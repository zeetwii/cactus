import sys # needed to exit
import matplotlib.pyplot as plt # needed for graphs
import matplotlib.animation as animation # needed for graphs
import numpy as np # needed for graph

import pika # needed for rabbitMQ

import time # needed for sleep
from threading import Thread # needed for threads

class SweepViewer:
    '''
    Simple python class to view wide sweeper output
    '''

    def __init__(self) -> None:
        self.minFreq = 0
        self.maxFreq = 6000
        self.maxHistory = 30

        tempList = [0] * (self.maxFreq-self.minFreq)
        self.dataList = []
        for i in range(self.maxHistory):
            self.dataList.append(tempList)

    def linkRabbit(self):
            """Setup and start listening for RabbitMQ messages
            """

            print("Listening for RabbitMQ messages")

            # RabbitMQ setup
            connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost'))
            channel = connection.channel()

            #channel.exchange_declare(exchange='freqSweep', exchange_type='fanout')
            channel.exchange_declare(exchange='scanSweep', exchange_type='fanout')

            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            # channel.queue_bind(exchange='freqSweep', queue=queue_name)
            channel.queue_bind(exchange='scanSweep', queue=queue_name)
            channel.basic_consume(queue=queue_name, on_message_callback=self.rabbitCallback, auto_ack=True)
            channel.start_consuming()

    def rabbitCallback(self, ch, method, properties, body):
        """Callback method for rabbitMQ

        Args:
            ch ([type]): [description]
            method ([type]): [description]
            properties ([type]): [description]
            body (String): The message body as a string
        """

        data = body.split( )
        newFreqs = [0] * (self.maxFreq-self.minFreq)

        freq = 0

        for i in range(0, len(data), 2):
            freq = int((int(data[i].decode()) / 1000000) - self.minFreq) # convert freq to index 

            val = round(float(data[i+1].decode()))

            if val != 0 :
                val = 100 + val
            
            newFreqs[freq] = val

            #print(f"Freq: {str(freq)} : {str(round(float(data[i+1].decode())))}")

        self.dataList.append(newFreqs)

        #if len(self.dataList) > self.maxHistory:
        self.dataList.pop(0)

        #print(str(newFreqs))
        

    def startViewer(self):
        self.rabbitThread = Thread(target=self.linkRabbit, daemon=True)
        self.rabbitThread.start()


if __name__ == "__main__":

    print("Starting Sweep Viewer")
    viewer = SweepViewer()
    viewer.startViewer()

    print("Press Ctrl + C to exit")

    x = np.arange(viewer.maxFreq)
    y = np.arange(viewer.maxHistory)
    X,Y = np.meshgrid(x,y)


    def animate(i, X,Y):
        
        Z = np.array(viewer.dataList)
        plt.pcolormesh(X, Y, Z, vmin=np.min(Z), vmax=np.max(Z), shading='auto')

    plt.close()
    fig = plt.figure()
    ani = animation.FuncAnimation(fig, animate, fargs=(X,Y), repeat = True)
    plt.show()

    #while True:
    #    input()





