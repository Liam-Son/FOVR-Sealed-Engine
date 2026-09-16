from __future__ import annotations
import os

REQUIRED_PROD_ENV=("FOVR_ENV","FOVR_DATA_LICENSE_MODE","FOVR_LOG_DIR")

def validate_environment():
    missing=[k for k in REQUIRED_PROD_ENV if not os.getenv(k)]
    mode=os.getenv("FOVR_ENV","dev").lower()
    license_mode=os.getenv("FOVR_DATA_LICENSE_MODE","unknown").lower()
    checks={
        "required_env":not missing,
        "commercial_data_in_prod":not (mode=="prod" and license_mode!="commercial"),
        "manifest_hmac_key":not (mode=="prod" and not os.getenv("FOVR_MANIFEST_HMAC_KEY")),
        "audit_hmac_key":not (mode=="prod" and not os.getenv("FOVR_AUDIT_HMAC_KEY")),
    }
    return {"pass":all(checks.values()),"checks":checks,"missing":missing,"mode":mode,"license_mode":license_mode}

def json_logger(name="fovr"):
    import logging, json
    logger=logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler=logging.StreamHandler()
    class Formatter(logging.Formatter):
        def format(self,record):
            return json.dumps({"level":record.levelname,"logger":record.name,"message":record.getMessage()})
    handler.setFormatter(Formatter())
    logger.addHandler(handler)
    return logger
