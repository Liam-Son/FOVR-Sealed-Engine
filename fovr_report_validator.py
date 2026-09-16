REQUIRED=("data_quality","methodology","costs","risk","limitations","provenance","dual_engine_status")
def validate_report(report):
    checks={k:bool(report.get(k) and str(report.get(k)).strip()) for k in REQUIRED}
    return {"pass":all(checks.values()),"checks":checks,"missing":[k for k,v in checks.items() if not v]}
