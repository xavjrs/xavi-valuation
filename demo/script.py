"""The explainer script: what is shown, the on-screen caption, and what the narrator says, step by step.

Edit the `say` lines to change the voiceover, then re-run demo/explainer.py. Captions (`text`) support **gold** emphasis.
Spoken lines are written for the ear: brand names and acronyms a synthetic voice mispronounces are avoided or spelled
phonetically. Crop coordinates are in the original 3840x2160 screenshot space (3300x2550 for the Excel export).
"""

VOICE = "en-GB-RyanNeural"      # Microsoft neural voice, British male
RATE = "-6%"                    # a touch slower than default for a calm, measured read

INTRO_SAY = ("Here's a valuation model of Shell and BP, built from their official accounts. "
             "In the next few minutes, I'll show you what it does, and how to read every screen.")

OV, SL = "s01_overview.png", "s02_slider_{:02d}.png"
BO, DE = "s05_buyout_{:02d}.png", "s06_deal_00.png"
FIN = [("s00_financials.png", (470, 690, 1100, 1660)), ("s00_financials.png", (2640, 690, 3305, 1660))]

CHAPTERS = [
    dict(n="01", title="Where the numbers come from", say="Chapter one. Where the numbers come from.", steps=[
        dict(crops=FIN, layout="row",
             text="Everything starts with Shell's and BP's **official annual accounts**, filed with the US regulator, the SEC. Five years of sales, profit, cash and debt.",
             say="Everything starts with the official annual reports that Shell and BP file with the American regulator, the S.E.C. "
                 "That gives five years of real figures: sales, profit, cash, and debt."),
        dict(crops=FIN, layout="row", hl=[(0, (470, 1060, 1100, 1135)), (1, (2640, 1060, 3305, 1135))],
             text="The model checks every year adds up, then **forecasts ten years ahead**: sales, costs, investment, tax and debt, all linked.",
             say="First, the model checks that every year adds up. Then it forecasts ten years ahead, with sales, costs, investment, tax and debt "
                 "all linked together. Change one, and everything else follows."),
    ]),
    dict(n="02", title="What is Shell worth?", say="Chapter two. What is Shell worth?", steps=[
        dict(crops=[(OV, (515, 445, 1194, 707)), (OV, (1225, 445, 1905, 707))], hl=[(0, (515, 445, 1194, 707))],
             text="Add up all the cash Shell should make in future, and adjust for money later being worth less than money now. That gives **2,621p a share**.",
             say="To value a company, you add up all the cash it should make in the future, and discount it, because a pound in ten years "
                 "is worth less than a pound today. Do that for Shell, and you get about two thousand, six hundred and twenty pence a share."),
        dict(crops=[(OV, (515, 445, 1194, 707)), (OV, (1225, 445, 1905, 707))], hl=[(1, (1225, 445, 1905, 707))],
             text="The stock market prices Shell at **3,836p**. On these assumptions, the shares look **about 32% expensive**.",
             say="The stock market, though, prices Shell at about three thousand, eight hundred and forty pence. "
                 "So on these assumptions, the shares look roughly a third too expensive."),
        dict(crops=[(OV, (515, 964, 3324, 1684))],
             text="Each gold bar is a different way of valuing Shell. The dashed line is today's price, and **almost every bar sits to its left**.",
             say="Each gold bar here is a different way of valuing the same company. The dashed line is today's share price. "
                 "Notice that almost every bar sits to the left of it."),
    ]),
    dict(n="03", title="Every number is live", say="Chapter three. Every number is live.", steps=[
        dict(seq=[SL.format(i) for i in range(9)], crops=[("SEQ", (40, 640, 560, 800)), ("SEQ", (816, 445, 1494, 707))],
             text="**EBIT margin** is how much of each pound of sales Shell keeps as operating profit. Push it up by **2 points**...",
             say="Here's the key idea. This slider is the operating profit margin: how much of each pound of sales Shell keeps as profit. "
                 "Watch what happens when I push it up by just two percentage points."),
        dict(crops=[(SL.format(8), (40, 640, 560, 800)), (SL.format(8), (816, 445, 1494, 707))], hl=[(1, (816, 445, 1494, 707))],
             text="...and the value jumps from 2,621p to **3,370p**. One assumption, **29% more value**. The inputs matter more than the maths.",
             say="The value jumps to about three thousand, three hundred and seventy pence. One assumption, and the answer moves by almost "
                 "thirty percent. That's why the inputs matter more than the maths."),
    ]),
    dict(n="04", title="How sure can we be?", say="Chapter four. How sure can we be?", steps=[
        dict(crops=[("s04_risk.png", (470, 710, 3250, 1460))],
             text="Instead of one forecast, the model plays out **10,000 possible futures**, with different growth, margins and interest rates.",
             say="A single forecast is really just one guess. So instead, the model plays out ten thousand possible futures, "
                 "each with different growth, margins, and interest rates."),
        dict(crops=[("s04_risk.png", (470, 710, 3250, 1460))], hl=[(0, (2105, 860, 3240, 1340))],
             text="Each bar counts how many futures landed at that value. Red is below today's price, gold above. Only **13%** say Shell is worth more than the market price.",
             say="Each bar counts how many of those futures landed at a particular value. Red is below today's price, gold is above it. "
                 "Only about one in eight futures says Shell is worth more than the market thinks."),
        dict(crops=[("s04_risk.png", (470, 1510, 1900, 2160))],
             text="The tornado ranks what matters most. **Revenue growth and margins** move the value far more than anything else.",
             say="This chart, called a tornado, ranks what matters most. Sales growth and margins move the value far more than anything else."),
    ]),
    dict(n="05", title="Could a buyout firm profit?", say="Chapter five. Could a buyout firm make money?", steps=[
        dict(crops=[(BO.format(0), (515, 1370, 3325, 1880))],
             text="A buyout firm buys a business **mostly with borrowed money**, pays the debt down from its cash, then sells. Here: Shell's fuel-station and lubricants arm.",
             say="A private equity firm buys a business mostly with borrowed money, uses the business's own cash to pay that debt down, "
                 "and then sells it a few years later. Here, the target is Shell's fuel station and lubricants division."),
        dict(crops=[(BO.format(0), (515, 925, 1190, 1190)), (BO.format(0), (1935, 630, 2610, 890))],
             text="At the price Shell itself trades on, **7.5x yearly profit or $59bn**, the buyer puts in $25bn of its own money and borrows the rest.",
             say="At the price Shell itself trades on, that's seven and a half times yearly profit, or about fifty nine billion dollars, "
                 "the buyer would put in twenty five billion of its own money, and borrow the rest."),
        dict(crops=[(BO.format(0), (515, 630, 1190, 890)), (BO.format(0), (2645, 630, 3325, 890))],
             text="Their return: just **6.6% a year**. Buyout firms aim for about 20%. To get there they could pay **no more than 5.8x**.",
             say="Their return would be just six and a half percent a year. Buyout firms usually aim for around twenty. "
                 "To get there, they could pay no more than about five point eight times profit."),
        dict(seq=[BO.format(i) for i in range(8)], crops=[("SEQ", (2000, 230, 2660, 350)), ("SEQ", (515, 630, 1190, 890))],
             text="Lower the price and the return climbs. Even at 5.75x it only reaches **11.7%**. **Shell's division is worth more to Shell than to a buyer.**",
             say="Lower the price, and the return climbs. But even at five and three quarter times, it only reaches about twelve percent. "
                 "In other words, this business is worth more to Shell than it would be to a buyer."),
    ]),
    dict(n="06", title="What if Shell bought BP?", say="Chapter six. What if Shell bought BP?", steps=[
        dict(crops=[(DE, (507, 712, 1203, 993)), (DE, (1216, 712, 1912, 993))],
             text="Shell offers BP's shareholders **764p a share, a 30% premium**, half in cash and half in new Shell shares. Total: **$156bn**.",
             say="Now imagine Shell buying BP. It offers BP's shareholders seven hundred and sixty four pence a share, a thirty percent premium, "
                 "paid half in cash and half in new Shell shares. That's a hundred and fifty six billion dollars in total."),
        dict(crops=[(DE, (507, 1006, 1203, 1287)), (DE, (1216, 1006, 1912, 1287))],
             text="**EPS accretion** asks: does Shell's profit per share go up? Year 1: **+3.1%**, rising to **+16.8%** by year 3 as savings arrive and debt is repaid.",
             say="The first question is simple: does Shell's profit per share go up? Here it does. By about three percent in the first year, "
                 "rising to nearly seventeen percent by year three, as cost savings arrive and the new debt is paid down."),
        dict(crops=[(DE, (2635, 1006, 3333, 1287))],
             text="But Shell would pay **$36bn** over BP's market value, far more than the **$20bn** the cost savings are worth. **It pays away more than it gains.**",
             say="But there's a catch. Shell would pay thirty six billion dollars more than BP is worth on the stock market, "
                 "while the cost savings are only worth about twenty billion. So Shell gives away more than it gains."),
    ]),
    dict(n="07", title="Building a portfolio", say="Chapter seven. Building a portfolio.", steps=[
        dict(crops=[("s07_frontier.png", (470, 270, 2050, 1190))],
             text="**13 shares** a UK investor might hold, measured in pounds. Each dot is one share: higher means more expected return, further right means more risk.",
             say="Next, thirteen shares that a British investor might own, all measured in pounds. Each dot is one share. "
                 "Higher means more expected return, and further right means more risk."),
        dict(crops=[("s07_frontier.png", (470, 270, 2050, 1190))], hl=[(0, (900, 560, 1720, 1020))],
             text="The gold curve is the **best return available for each level of risk**. Each diamond is a different way to split your money.",
             say="The gold curve shows the best return you can get for each level of risk. Each diamond is a different way of splitting your money "
                 "between the shares."),
        dict(crops=[("s07b_backtest.png", (470, 270, 3245, 1650))], hl=[(0, (2650, 1100, 3020, 1640))],
             text="Replaying 2023 to 2026 with **no hindsight**: every strategy beat the FTSE 100, and **simply splitting your money equally** did as well as the clever ones once risk is counted.",
             say="Then we replay the last three years, with no hindsight. Every strategy beat the Footsie one hundred. And interestingly, "
                 "simply splitting your money equally did just as well as the clever strategies, once you allow for risk."),
    ]),
    dict(n="08", title="Can you trust it?", say="Chapter eight. Can you trust it?", steps=[
        dict(crops=[("xl_Checks.png", (50, 1310, 2950, 2480))], hl=[(0, (2600, 2390, 2950, 2480))],
             text="Every key number was rebuilt independently in **Excel: 1,082 live formulas**. All **36** checks match the Python model to within a billionth.",
             say="To check the work, every key number was rebuilt independently in Excel, using over a thousand live formulas. "
                 "All thirty six checks match the main model, to within a billionth."),
        dict(crops=[("s08_audit.png", (515, 1440, 1194, 1703)), ("s08_audit.png", (1225, 1440, 1905, 1703))],
             text="Plus **86 automatic checks**: the accounts balance, the maths is consistent, and no step peeks into the future.",
             say="On top of that, eighty six automatic checks confirm that the accounts balance, the maths is consistent, "
                 "and nothing peeks into the future."),
    ]),
]

CAVEAT = ("What it isn't", "The answers depend on assumptions I chose: growth, margins, discount rates. Change them and the conclusions change. "
                           "**A model, not investment advice.**")
CAVEAT_SAY = ("One last thing. These answers depend on assumptions I chose: growth, margins, and discount rates. "
              "Change them, and the conclusions change. So treat this as a model, not as investment advice.")
