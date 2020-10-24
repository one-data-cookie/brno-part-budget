from apscheduler.schedulers.blocking import BlockingScheduler
from main import brno_part_budget

sched = BlockingScheduler()
sched.add_job(cronjob, 'interval', minutes=5)

sched.start()
