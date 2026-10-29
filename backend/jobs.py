"""Background job runner.

Research jobs run in worker threads so the UI stays responsive and reports
real progress. A job is honest about its lifecycle: if the hosting environment
stops the process, the job stops too — we never claim otherwise.
"""
import threading
import time

from backend.research.engine import run_research

_threads: dict[str, threading.Thread] = {}
_cancel_flags: dict[str, bool] = {}
_lock = threading.Lock()


def start_job(db, config, job_id: str, plan: dict):
    with _lock:
        _cancel_flags[job_id] = False

    def _target():
        try:
            run_research(db, config, job_id, plan,
                         cancel_check=lambda: _cancel_flags.get(job_id, False))
        except Exception as exc:  # never leave a job stuck in "running"
            import json
            db.update_job(
                job_id, status="failed", progress_message=f"Research failed: {exc}",
                error=str(exc)[:2000], finished_at=time.time(),
                summary_json=json.dumps({"note": f"Failed: {exc}"}),
            )
        finally:
            with _lock:
                _threads.pop(job_id, None)
                _cancel_flags.pop(job_id, None)

    t = threading.Thread(target=_target, name=f"grabresult-job-{job_id}", daemon=True)
    with _lock:
        _threads[job_id] = t
    t.start()


def cancel_job(db, job_id: str) -> bool:
    with _lock:
        if job_id in _threads:
            _cancel_flags[job_id] = True
            return True
    job = db.get_job(job_id)
    if job and job["status"] in ("queued", "running"):
        db.update_job(job_id, status="cancelled", finished_at=time.time(),
                      progress_message="Cancelled by user.")
        return True
    return False


def job_is_active(job_id: str) -> bool:
    with _lock:
        return job_id in _threads
