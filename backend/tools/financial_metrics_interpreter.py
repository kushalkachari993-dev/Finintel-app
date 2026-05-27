class FinancialMetricsInterpreter:

    # ---------------------------------------------------
    # MAIN METHOD
    # ---------------------------------------------------

    def generate_interpretation(
        self,
        stock_data: dict
    ):

        sector = (
            stock_data
            .get("sector", "")
            or ""
        ).lower()

        interpretation = {

            "roe_analysis":
            self.analyze_roe(
                stock_data,
                sector
            ),

            "debt_analysis":
            self.analyze_debt(
                stock_data,
                sector
            ),

            "valuation_analysis":
            self.analyze_valuation(
                stock_data,
                sector
            ),

            "growth_analysis":
            self.analyze_growth(
                stock_data
            ),

            "margin_analysis":
            self.analyze_margins(
                stock_data,
                sector
            ),

            "dividend_analysis":
            self.analyze_dividend(
                stock_data
            )
        }

        return interpretation

    # ---------------------------------------------------
    # ROE ANALYSIS
    # ---------------------------------------------------

    def analyze_roe(
        self,
        stock_data,
        sector
    ):

        roe = stock_data.get("roe_raw")

        if roe is None:

            return "ROE data unavailable."

        roe_percent = roe

        # -----------------------------------
        # BANKING
        # -----------------------------------

        if "financial" in sector \
        or "bank" in sector:

            if roe_percent >= 15:

                return (
                    f"Strong ROE "
                    f"({roe_percent:.2f}%) "
                    f"for a banking/financial company, "
                    f"indicating healthy profitability."
                )

            elif roe_percent >= 10:

                return (
                    f"Moderate ROE "
                    f"({roe_percent:.2f}%) "
                    f"for a banking company."
                )

            else:

                return (
                    f"Weaker ROE "
                    f"({roe_percent:.2f}%) "
                    f"for a banking company."
                )

        # -----------------------------------
        # IT / TECHNOLOGY
        # -----------------------------------

        elif "technology" in sector \
        or "it" in sector:

            if roe_percent >= 25:

                return (
                    f"Very strong ROE "
                    f"({roe_percent:.2f}%) "
                    f"indicates excellent capital efficiency "
                    f"for an IT company."
                )

            elif roe_percent >= 15:

                return (
                    f"Healthy ROE "
                    f"({roe_percent:.2f}%) "
                    f"for a technology company."
                )

            else:

                return (
                    f"Relatively weaker ROE "
                    f"({roe_percent:.2f}%) "
                    f"for a technology company."
                )

        # -----------------------------------
        # GENERAL
        # -----------------------------------

        else:

            if roe_percent >= 20:

                return (
                    f"Strong ROE "
                    f"({roe_percent:.2f}%) "
                    f"indicates good profitability."
                )

            elif roe_percent >= 12:

                return (
                    f"Moderate ROE "
                    f"({roe_percent:.2f}%) "
                    f"indicates stable profitability."
                )

            else:

                return (
                    f"Lower ROE "
                    f"({roe_percent:.2f}%) "
                    f"may indicate weaker profitability."
                )

    # ---------------------------------------------------
    # DEBT ANALYSIS
    # ---------------------------------------------------

    def analyze_debt(
        self,
        stock_data,
        sector
    ):

        debt = stock_data.get(
            "debt_to_equity_raw"
        )

        if debt is None:

            return (
                "Debt-to-equity data unavailable."
            )

        if "financial" in sector \
        or "bank" in sector:

            return (
                "Debt metrics for banks and "
                "financial institutions should "
                "be interpreted differently due "
                "to their business model."
            )

        elif "technology" in sector \
        or "it" in sector:

            if debt < 30:

                return (
                    f"Low debt profile "
                    f"(D/E: {debt:.2f}) "
                    f"is a positive sign for "
                    f"a technology company."
                )

            else:

                return (
                    f"Higher debt levels "
                    f"(D/E: {debt:.2f}) "
                    f"may increase financial risk "
                    f"for a technology company."
                )

        elif "telecom" in sector:

            return (
                f"Telecom businesses often operate "
                f"with higher debt levels. "
                f"Current D/E: {debt:.2f}."
            )

        else:

            if debt < 50:

                return (
                    f"Conservative debt profile "
                    f"(D/E: {debt:.2f})."
                )

            elif debt < 100:

                return (
                    f"Moderate debt levels "
                    f"(D/E: {debt:.2f})."
                )

            else:

                return (
                    f"High leverage "
                    f"(D/E: {debt:.2f}) "
                    f"may increase financial risk."
                )

    # ---------------------------------------------------
    # VALUATION ANALYSIS
    # ---------------------------------------------------

    def analyze_valuation(
        self,
        stock_data,
        sector
    ):

        pe = stock_data.get("pe_ratio")

        if pe is None:

            return "Valuation data unavailable."

        if "technology" in sector \
        or "it" in sector:

            if pe < 20:

                return (
                    f"P/E ratio of {pe:.2f} "
                    f"appears reasonable for "
                    f"a technology company."
                )

            elif pe < 35:

                return (
                    f"P/E ratio of {pe:.2f} "
                    f"suggests moderate premium valuation."
                )

            else:

                return (
                    f"High valuation "
                    f"(P/E: {pe:.2f}) "
                    f"may imply elevated growth expectations."
                )

        else:

            if pe < 15:

                return (
                    f"P/E ratio of {pe:.2f} "
                    f"appears relatively inexpensive."
                )

            elif pe < 30:

                return (
                    f"P/E ratio of {pe:.2f} "
                    f"appears reasonably valued."
                )

            else:

                return (
                    f"Higher valuation "
                    f"(P/E: {pe:.2f}) "
                    f"may indicate elevated expectations."
                )

    # ---------------------------------------------------
    # GROWTH ANALYSIS
    # ---------------------------------------------------

    def analyze_growth(
        self,
        stock_data
    ):

        growth = stock_data.get(
            "revenue_growth_raw"
        )

        if growth is None:

            return (
                "Revenue growth data unavailable."
            )

        growth_percent = growth

        if growth_percent >= 15:

            return (
                f"Strong revenue growth "
                f"({growth_percent:.2f}%) "
                f"indicates healthy business expansion."
            )

        elif growth_percent >= 5:

            return (
                f"Moderate revenue growth "
                f"({growth_percent:.2f}%) "
                f"suggests stable business momentum."
            )

        elif growth_percent >= 0:

            return (
                f"Low revenue growth "
                f"({growth_percent:.2f}%) "
                f"may indicate slower expansion."
            )

        else:

            return (
                f"Negative revenue growth "
                f"({growth_percent:.2f}%) "
                f"may indicate business challenges."
            )

    # ---------------------------------------------------
    # MARGIN ANALYSIS
    # ---------------------------------------------------

    def analyze_margins(
        self,
        stock_data,
        sector
    ):

        operating_margin = stock_data.get(
            "operating_margin_raw"
        )

        if operating_margin is None:

            return (
                "Margin data unavailable."
            )

        margin_percent = operating_margin

        if "technology" in sector \
        or "it" in sector:

            if margin_percent >= 20:

                return (
                    f"Strong operating margin "
                    f"({margin_percent:.2f}%) "
                    f"indicates efficient operations."
                )

            else:

                return (
                    f"Moderate operating margin "
                    f"({margin_percent:.2f}%)."
                )

        else:

            if margin_percent >= 15:

                return (
                    f"Healthy operating margin "
                    f"({margin_percent:.2f}%)."
                )

            else:

                return (
                    f"Lower operating margin "
                    f"({margin_percent:.2f}%) "
                    f"may indicate profitability pressure."
                )

    # ---------------------------------------------------
    # DIVIDEND ANALYSIS
    # ---------------------------------------------------

    def analyze_dividend(
        self,
        stock_data
    ):

        dividend = stock_data.get(
            "dividend_yield_raw"
        )

        if dividend is None:

            return (
                "Dividend yield data unavailable."
            )

        if dividend >= 4:

            return (
                f"High dividend yield "
                f"({dividend:.2f}%) "
                f"may appeal to income-focused investors."
            )

        elif dividend >= 1:

            return (
                f"Moderate dividend yield "
                f"({dividend:.2f}%)."
            )

        else:

            return (
                f"Low dividend yield "
                f"({dividend:.2f}%)."
            )