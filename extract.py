"""Extract annual IFRS statements for Shell and BP from SEC EDGAR 20-F XBRL facts into tidy CSVs."""
import json, datetime as dt
import pandas as pd

YEARS = ["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]

# model line -> candidate XBRL tags (first one found wins)
MAP = {
    "revenue": ["Revenue"],
    "pbt": ["ProfitLossBeforeTax"],
    "tax": ["IncomeTaxExpenseContinuingOperations"],
    "net_income": ["ProfitLoss"],
    "net_income_parent": ["ProfitLossAttributableToOwnersOfParent"],
    "da": ["AdjustmentsForDepreciationAndAmortisationExpense", "DepreciationAndAmortisationExpense"],
    "finance_costs": ["InterestExpense", "FinanceCosts"],
    "cfo": ["CashFlowsFromUsedInOperatingActivities"],
    "cfi": ["CashFlowsFromUsedInInvestingActivities"],
    "cff": ["CashFlowsFromUsedInFinancingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets",
              "PurchaseOfOtherLongtermAssetsClassifiedAsInvestingActivities"],
    "dividends_paid": ["DividendsPaid"],
    "buybacks": ["PaymentsToAcquireOrRedeemEntitysShares"],
    "total_assets": ["Assets"],
    "current_assets": ["CurrentAssets"],
    "cash": ["CashAndCashEquivalents"],
    "inventories": ["Inventories"],
    "receivables": ["TradeAndOtherCurrentReceivables"],
    "ppe": ["PropertyPlantAndEquipmentIncludingRightofuseAssets", "PropertyPlantAndEquipment"],
    "goodwill": ["Goodwill"],
    "intangibles": ["IntangibleAssetsOtherThanGoodwill"],
    "total_liabilities": ["Liabilities"],
    "current_liabilities": ["CurrentLiabilities"],
    "payables": ["TradeAndOtherCurrentPayables"],
    "debt_current": ["CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"],
    "debt_long": ["LongtermBorrowings"],
    "lease_liabilities": ["LeaseLiabilities"],
    "equity_total": ["Equity"],
    "equity_parent": ["EquityAttributableToOwnersOfParent"],
    "nci": ["NoncontrollingInterests"],
    "net_debt_reported": ["NetDebt"],
    # helper lines used to derive underlying D&A and lease principal (see build())
    "finance_income": ["FinanceIncome"],
    "jv_share": ["ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod"],
    "equity_investments": ["InvestmentAccountedForUsingEquityMethod"],
    "_decom": ["ProvisionForDecommissioningRestorationAndRehabilitationCosts"],
    "_provisions_total": ["Provisions"],
    "_pension_liab": ["NoncurrentRecognisedLiabilitiesDefinedBenefitPlan"],
    "_pension_asset": ["NoncurrentRecognisedAssetsDefinedBenefitPlan"],
    "_op_profit": ["ProfitLossFromOperatingActivities"],
    "_impairment_net_reported": ["ImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"],
    "_impairment_loss": ["ImpairmentLossRecognisedInProfitOrLoss"],
    "_impairment_reversal": ["ReversalOfImpairmentLossRecognisedInProfitOrLoss"],
    "_lease_cash_outflow": ["CashOutflowForLeases"],
    "_lease_interest": ["InterestExpenseOnLeaseLiabilities"],
    "_lease_principal_reported": ["PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities"],
}

# Shell's cash-flow D&A add-back includes net impairments (D&A + impairment - reversals);
# BP's is depreciation/depletion/amortisation only (impairment is reported separately).
DA_INCLUDES_IMPAIRMENT = {"shell": True, "bp": False}

def annual(facts, tag):
    c = facts.get(tag)
    if not c:
        return {}
    out = {}
    for rows in c["units"].values():
        for r in rows:
            if r.get("form") != "20-F" or r["end"] not in YEARS:
                continue
            if "start" in r:
                days = (dt.date.fromisoformat(r["end"]) - dt.date.fromisoformat(r["start"])).days
                if not 350 <= days <= 380:
                    continue
            if r["end"] not in out or r["filed"] > out[r["end"]][1]:
                out[r["end"]] = (r["val"] / 1e6, r["filed"], tag)
    return out

def build(name):
    facts = json.load(open(f"data/raw/{name}_companyfacts.json"))["facts"]["ifrs-full"]
    rows, src = {}, {}
    for line, tags in MAP.items():
        merged = {}
        for t in tags:                      # fill gaps from later tags year by year
            for y, v in annual(facts, t).items():
                merged.setdefault(y, v)
        rows[line] = {y[:4]: merged[y][0] for y in merged}
        src[line] = sorted({v[2] for v in merged.values()})
    df = pd.DataFrame(rows).T.reindex(columns=[y[:4] for y in YEARS])
    imp_net = df.loc["_impairment_net_reported"].fillna(
        df.loc["_impairment_loss"].fillna(0) - df.loc["_impairment_reversal"].fillna(0))
    df.loc["impairment_net"] = imp_net
    df.loc["da_underlying"] = df.loc["da"] - (imp_net if DA_INCLUDES_IMPAIRMENT[name] else 0)
    # lease principal: reported where available, else total lease cash outflow less lease interest
    df.loc["lease_principal"] = df.loc["_lease_principal_reported"].fillna(
        df.loc["_lease_cash_outflow"] - df.loc["_lease_interest"])
    # debt-like items for the EV -> equity bridge
    df.loc["provisions_debt_like"] = df.loc["_decom"].fillna(df.loc["_provisions_total"])
    df.loc["pension_deficit"] = (df.loc["_pension_liab"].fillna(0) - df.loc["_pension_asset"].fillna(0)).clip(lower=0)
    # operating EBIT excluding associates/JVs and non-operating finance items:
    #   Shell: no reported operating profit -> PBT + interest expense - finance income - JV share
    #   BP: reported profit from operating activities - JV share
    if name == "shell":
        df.loc["ebit_ops"] = df.loc["pbt"] + df.loc["finance_costs"] - df.loc["finance_income"] - df.loc["jv_share"]
    else:
        df.loc["ebit_ops"] = df.loc["_op_profit"] - df.loc["jv_share"]
    df = df.drop(index=[i for i in df.index if i.startswith("_")])
    df.index.name = "line_usd_m"
    df.to_csv(f"data/clean/{name}_annual.csv")
    return df, src

for name in ["shell", "bp"]:
    df, src = build(name)
    print(f"\n===== {name.upper()}  missing cells: {int(df.isna().sum().sum())}")
    miss = df[df.isna().any(axis=1) & (df.index != "finance_income")]  # finance_income is Shell-only
    if len(miss): print("gaps:\n", miss.isna().apply(lambda r: ",".join(c for c in df.columns if r[c]), axis=1).to_string())
    chk = pd.DataFrame({
        "A - (L+E)": df.loc["total_assets"] - df.loc["total_liabilities"] - df.loc["equity_total"],
        "E - (parent+NCI)": df.loc["equity_total"] - df.loc["equity_parent"] - df.loc["nci"],
        "PBT - tax - NI": df.loc["pbt"] - df.loc["tax"] - df.loc["net_income"],
        "FCF (CFO-capex)": df.loc["cfo"] - df.loc["capex"],
    }).round(1)
    print(chk.T.to_string())
    print("sources used for capex:", src["capex"], "| finance costs:", src["finance_costs"])
