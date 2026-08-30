import re
from typing import Dict, Any

class GSTINValidatorService:
    STATE_CODES = {
        "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
        "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
        "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
        "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
        "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
        "24": "Gujarat", "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
        "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
        "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
        "38": "Ladakh"
    }

    CHAR_MAP = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    @classmethod
    def validate_checksum(cls, gstin: str) -> bool:
        if len(gstin) != 15:
            return False
            
        input_chars = gstin[:14]
        check_digit = gstin[14]

        total = 0
        for i, char in enumerate(input_chars):
            val = cls.CHAR_MAP.find(char)
            if val == -1:
                return False
            
            # 1st char (index 0) * 1, 2nd char (index 1) * 2, 3rd char (index 2) * 1, etc.
            factor = 1 if (i % 2 == 0) else 2
            product = val * factor
            
            # Sum of quotient and remainder in base 36
            total += (product // 36) + (product % 36)

        remainder = total % 36
        expected_check_val = (36 - remainder) % 36
        expected_check_char = cls.CHAR_MAP[expected_check_val]

        return check_digit == expected_check_char

    @classmethod
    def verify_gstin(cls, gstin: str) -> Dict[str, Any]:
        if not gstin or not isinstance(gstin, str):
            return {"valid": False, "error": "GSTIN missing or empty", "status": "UNVERIFIED"}

        clean_gstin = re.sub(r"[^A-Za-z0-9]", "", gstin).upper()

        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}$"
        
        if not re.match(pattern, clean_gstin):
            return {
                "gstin": clean_gstin,
                "valid": False,
                "error": f"Invalid format structure (Length: {len(clean_gstin)})",
                "status": "INVALID"
            }

        state_code = clean_gstin[:2]
        pan = clean_gstin[2:12]
        state_name = cls.STATE_CODES.get(state_code, "Unknown State")

        if state_name == "Unknown State":
            return {
                "gstin": clean_gstin,
                "valid": False,
                "error": f"Invalid State Code '{state_code}'",
                "status": "INVALID"
            }

        is_checksum_valid = cls.validate_checksum(clean_gstin)

        return {
            "gstin": clean_gstin,
            "valid": is_checksum_valid,
            "state_code": state_code,
            "state_name": state_name,
            "extracted_pan": pan,
            "checksum_valid": is_checksum_valid,
            "registration_status": "ACTIVE" if is_checksum_valid else "INVALID",
            "error": None if is_checksum_valid else "Checksum digit verification failed"
        }

gstin_validator = GSTINValidatorService()