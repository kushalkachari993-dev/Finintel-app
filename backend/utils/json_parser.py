import json
import re


class JSONParser:

    @staticmethod
    def parse(raw_output: str):

        if not raw_output:

            return None

        try:

            cleaned = re.sub(
                r"```json|```",
                "",
                raw_output
            ).strip()

            return json.loads(cleaned)

        except Exception:

            pass

        try:

            match = re.search(
                r"\{.*\}",
                cleaned,
                re.DOTALL
            )

            if not match:

                return None

            return json.loads(
                match.group(0)
            )

        except Exception:

            return None
