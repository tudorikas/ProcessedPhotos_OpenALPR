import pika
import json

"""
    File RabbitMqPut.py have the role to manage the connection to RabbitMq,
    and a function that allow to send message to queue
"""
class RabbitMq:
    """ The main class that will Work with Rabbit. """
    def __init__(self,RabbitmqQueue,RabbitmqServer):
        """Initialize the variables."""
        self.RabbitmqQueue=RabbitmqQueue
        self.RabbitmqServer=RabbitmqServer

    def sendToRabbit(self,data):
        """ Send a message to the queue predefined with max length 200
        Max length is used for reducing RAM usage"""
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.RabbitmqServer))
        channel = connection.channel()
        args = {"x-max-length": 200}
        channel.queue_declare(queue=self.RabbitmqQueue, durable=True,arguments=args)
        channel.basic_publish(exchange='', routing_key=self.RabbitmqQueue, body=json.dumps(data))
        connection.close()
