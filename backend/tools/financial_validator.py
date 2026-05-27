class FinancialValidator:

    # ---------------------------------------------------
    # VALIDATE DIVIDEND YIELD
    # ---------------------------------------------------

    @staticmethod
    def validate_dividend_yield(value):

        if value is None:
            return None

        try:

            value = float(value)

            # -----------------------------------
            # INVALID IF TOO HIGH
            # -----------------------------------

            if value < 0 or value > 25:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE PE
    # ---------------------------------------------------

    @staticmethod
    def validate_pe(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < 0 or value > 500:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE PB
    # ---------------------------------------------------

    @staticmethod
    def validate_pb(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < 0 or value > 100:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE ROE
    # ---------------------------------------------------

    @staticmethod
    def validate_roe(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < -100 or value > 100:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE MARGIN
    # ---------------------------------------------------

    @staticmethod
    def validate_margin(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < -100 or value > 100:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE REVENUE GROWTH
    # ---------------------------------------------------

    @staticmethod
    def validate_growth(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < -500 or value > 500:

                return None

            return value

        except Exception:

            return None

    # ---------------------------------------------------
    # VALIDATE DEBT/EQUITY
    # ---------------------------------------------------

    @staticmethod
    def validate_debt_to_equity(value):

        if value is None:
            return None

        try:

            value = float(value)

            if value < 0 or value > 1000:

                return None

            return value

        except Exception:

            return None