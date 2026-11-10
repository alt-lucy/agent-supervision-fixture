def weekly_to_monthly(weekly: float) -> float:
    return round(weekly * 4, 2)


def format_gbp(amount: float) -> str:
    return f"£{amount:,.2f}"
