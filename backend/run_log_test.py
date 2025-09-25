from app.logging_utils import setup_logger, log_kv
log = setup_logger("ingestion")  # writes to logs/ingestion.log
log.info("hello-from-logger")
log_kv(log, stage="sanity", ok=True)
print("wrote logs/ingestion.log")
