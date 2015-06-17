Pika stable version
-------------------
The Pika package (a python client for RabbitMQ) is installed with the origin/master of the source (7f222c29ab, as of July 7th, 2015), using an egg, instead of taking the last stable version from PyPI (0.9.14, as of the aformentioned day) because the latter contains the following critical bug: 

https://github.com/pika/pika/issues/507

This bug is reproducible when using RackAttack-Physical on the following
commit: 14c29ed. The consecuences of the bug are one (or more) of the following
two, when running (roughly) 15 allocations concurrently:

* 'checkin' messages don't arrive from hosts to the RackAttack.
* RackAttack crashes, since the connection to the RabbitMQ server was closed,
  with the following error message in RabbitMQ's log:

```
=ERROR REPORT==== 3-May-2015::16:04:46 ===
AMQP connection <0.210.0> (running), channel 1 - error:
{amqp_error,unexpected_frame,
            "expected content body, got non content body frame instead",
                        'basic.publish'}
```

This bug was fixed by commit de8b545 ('Ensure frames can not be interspersed
on send') which was written after 0.9.14 (and therefore we use the egg).
