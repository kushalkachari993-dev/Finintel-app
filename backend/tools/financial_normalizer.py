import re


class FinancialNormalizer:

    # ---------------------------------------------------
    # NORMALIZE PERCENTAGE
    # ---------------------------------------------------

    @staticmethod
    def normalize_percentage(value):

        if value is None:
            return None

        try:

            value = float(value)

            # -----------------------------------
            # YAHOO SOMETIMES RETURNS:
            # 0.18 instead of 18
            # -----------------------------------

            if abs(value) <= 1:

                value *= 100

            return round(value, 2)

        except Exception:

            return None

    # ---------------------------------------------------
    # NORMALIZE RATIO
    # ---------------------------------------------------

    @staticmethod
    def normalize_ratio(value):

        if value is None:
            return None

        try:

            return round(float(value), 2)

        except Exception:

            return None

    # ---------------------------------------------------
    # NORMALIZE MARKET CAP
    # ---------------------------------------------------

    @staticmethod
    def normalize_market_cap(value):

        if value is None:
            return "N/A"

        try:

            value = float(value)

            crore = (
                value / 10000000
            )

            # -----------------------------------
            # LAKH CRORE
            # -----------------------------------

            if crore >= 100000:

                lakh_cr = (
                    crore / 100000
                )

                return (
                    f"INR {lakh_cr:.2f} "
                    f"Lakh Cr"
                )

            # -----------------------------------
            # CRORE
            # -----------------------------------

            return (
                f"INR {crore:.2f} Cr"
            )

        except Exception:

            return "N/A"

    # ---------------------------------------------------
    # FORMAT PERCENT STRING
    # ---------------------------------------------------

    @staticmethod
    def format_percentage(value):

        if value is None:

            return "N/A"

        return f"{value:.2f}%"

    # ---------------------------------------------------
    # FORMAT RATIO
    # ---------------------------------------------------

    @staticmethod
    def format_ratio(value):

        if value is None:

            return "N/A"

        return round(value, 2)

    # ---------------------------------------------------
    # USD TEXT TO INR TEXT
    # ---------------------------------------------------

    @staticmethod
    def format_inr_amount(
        amount_inr: float
    ):
        crore = (
            amount_inr
            / 10000000
        )

        if crore >= 100000:

            return (
                f"INR {crore / 100000:.2f} "
                "Lakh Cr"
            )

        return (
            f"INR {crore:.2f} Cr"
        )

    @classmethod
    def usd_amount_to_inr_text(
        cls,
        amount: float,
        unit: str,
        usd_to_inr_rate: float
    ):
        multiplier = {
            "million": 1000000,
            "billion": 1000000000,
            "trillion": 1000000000000
        }.get(
            unit.lower(),
            1
        )

        amount_inr = (
            amount
            * multiplier
            * usd_to_inr_rate
        )

        return cls.format_inr_amount(
            amount_inr
        )

    @classmethod
    def normalize_usd_amounts_in_text(
        cls,
        text: str,
        usd_to_inr_rate: float
    ):
        if not isinstance(
            text,
            str
        ):

            return text

        pattern = re.compile(
            r"\$(\d+(?:\.\d+)?)\s*"
            r"(million|billion|trillion)\b",
            flags=re.IGNORECASE
        )

        def replace(match):

            amount = float(
                match.group(1)
            )
            unit = match.group(2)

            return cls.usd_amount_to_inr_text(
                amount=amount,
                unit=unit,
                usd_to_inr_rate=usd_to_inr_rate
            )

        return pattern.sub(
            replace,
            text
        )

    @classmethod
    def normalize_usd_amounts(
        cls,
        value,
        usd_to_inr_rate: float
    ):
        if isinstance(
            value,
            str
        ):

            return cls.normalize_usd_amounts_in_text(
                value,
                usd_to_inr_rate
            )

        if isinstance(
            value,
            list
        ):

            return [
                cls.normalize_usd_amounts(
                    item,
                    usd_to_inr_rate
                )
                for item in value
            ]

        if isinstance(
            value,
            dict
        ):

            return {
                key: cls.normalize_usd_amounts(
                    item,
                    usd_to_inr_rate
                )
                for key, item in value.items()
            }

        return value
