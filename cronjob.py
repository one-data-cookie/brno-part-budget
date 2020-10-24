from apscheduler.schedulers.blocking import BlockingScheduler
from main import brno_part_budget

sched = BlockingScheduler()
sched.add_job(brno_part_budget, 'interval', minutes=1)

sched.start()
