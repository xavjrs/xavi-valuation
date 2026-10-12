import math
import pytest
from model.three_statement import load_history, default_assumptions, forecast, SCENARIOS, BASE_YEAR


@pytest.fixture(scope="module", params=["shell", "bp"])
def hist(request):
    return load_history(request.param)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_balance_sheet_balances(hist, scenario):
    out = forecast(hist, default_assumptions(hist, scenario))
    assert out["balance_sheet"].loc["balance_check"].abs().max() < 1e-6


def test_cash_roll_forward(hist):
    out = forecast(hist, default_assumptions(hist))
    cf, bs = out["cash_flow"], out["balance_sheet"]
    opening = float(hist.loc["cash", BASE_YEAR])
    for yr in cf.columns:
        assert math.isclose(opening + cf.loc["net_change_in_cash", yr], bs.loc["cash", yr], abs_tol=1e-6)
        opening = bs.loc["cash", yr]


def test_net_income_ties_across_statements(hist):
    out = forecast(hist, default_assumptions(hist))
    assert (out["income_statement"].loc["net_income"] - out["cash_flow"].loc["net_income"]).abs().max() < 1e-9


def test_scenarios_are_ordered(hist):
    ni = {s: forecast(hist, default_assumptions(hist, s))["income_statement"].loc["net_income"].sum() for s in SCENARIOS}
    assert ni["bear"] < ni["base"] < ni["bull"]
