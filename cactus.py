# RF analysis script

import subprocess # needed for hackrf sweep
import sys # needed for rabbit
import time # needed for sleep
from threading import Thread # needed for threads

import pika # needed for rabbitMQ

from sklearn.cluster import KMeans # needed for clustering
from sklearn.cluster import DBSCAN # needed for DBSCAN clustering
import numpy as np # needed for clustering
from sklearn.neighbors import NearestNeighbors # needed for helping find epsilon
from kneed import KneeLocator # needed for helping to find epsilon

class Cactus:
    """
    Class to handle RF stuff
    """

    def __init__(self, minFreq=1, maxFreq=6000, ampEnable=1, lnaGain=40, vgaGain=30, binSize=100000, dbmAdjust=0, clusterHistory=60):
        """
        Initialization method

        Args:
            minFreq (int, optional): The min frequency to scan in MHz. Defaults to 1.
            maxFreq (int, optional): The max frequency to scan in MHz. Defaults to 6000.
            ampEnable (int, optional): 0 to disable amplifier, anything else to enable. Defaults to 1.
            lnaGain (int, optional): LNA gain (0-40 dB). Defaults to 40.
            vgaGain (int, optional): VGA gain (0-62 dB). Defaults to 40.
            binSize (int, optional): The width of each frequency bin in Hertz. Defaults to 100000.
            dbmAdjust (float, optional): Adds to the calculated power cutoff for minimum dBm to be considered a signal. Defaults to 0.
            clusterHistory (int, optional): The amount of previous runs to include when clustering, defaults to 60.
        """

        # rabbitMQ setup
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='signalSweep', exchange_type='fanout')
        self.channel.exchange_declare(exchange='scanSweep', exchange_type='fanout')
        
        # variable setup
        self.minFreq = int(minFreq)
        self.maxFreq = int(maxFreq)
        self.lnaGain = int(lnaGain)
        self.vgaGain = int(vgaGain)
        self.binSize = int(binSize)
        self.dbmAdjust = float(dbmAdjust)

        # set amp enable field
        if ampEnable >= 1:
            self.ampEnable = 1
        else:
            self.ampEnable = 0

        # variables for clustering
        self.clusterHistory = clusterHistory
        self.dataList = []
        self.dbList = []

    def __publishScan(self, freqList, dbList):
        """
        Internal method to publish scan results via RabbitMQ

        Args:
            freqList (list): list of frequencies
            dbList (list): list of recorded power levels
        """

        # initialize message and find min length
        message = ''
        listLen = min(len(freqList), len(dbList))

        # build message
        for i in range(listLen):
            message += f"{str(freqList[i])} {str(dbList[i])} "

        # transmit over RabbitMQ
        self.channel.basic_publish(exchange='scanSweep', routing_key='', body=message)
        #print(message)
        #print('')

    def __publishSignal(self, signalList):
        """
        Internal method to publish signal results via RabbitMQ

        Args:
            signalList (list): list of detected signals
        """

        message = ''
        for i in range(len(signalList)):
            message += f"{str(signalList[i][0])} {str(signalList[i][1])} {str(signalList[i][2])} {str(signalList[i][3])} "

        # transmit over RabbitMQ
        self.channel.basic_publish(exchange='signalSweep', routing_key='', body=message)
        #print(message)

    def __clusterData(self, dataList):
        """
        Generates clustering data

        Args:
            dataList (list): the list of data points to cluster

        Returns:
            list: list of clustered points
        """

        # gets distance from all neighbours
        data = np.asarray(dataList)
        neighbors = NearestNeighbors(n_neighbors=11).fit(data)
        distances, indices = neighbors.kneighbors(data)
        distances = np.sort(distances[:,len(distances[0])-1], axis=0)

        # find knee point
        knee = KneeLocator(np.arange(len(distances)), distances, S=1, curve='convex', direction='increasing', interp_method='polynomial')
        #print(str(knee.knee))

        # use knee point to calculate clusters
        dbClusters = DBSCAN(eps=distances[knee.knee], min_samples=10).fit(data)

        # Number of Clusters
        nClusters=len(set(dbClusters.labels_))-(1 if -1 in dbClusters.labels_ else 0)
        #print(str(nClusters))
        
        # creates a list of lists to hold each point in its cluster
        clusterPoints = []
        for i in range(nClusters):
            clusterPoints.append([])

        #print(str(clusterPoints))

        # put each pixel in the cluster list its a part of
        for i in range(len(dataList)):
            if dbClusters.labels_[i] != -1: # if not a un-clustered point, add to list
                clusterPoints[dbClusters.labels_[i]].append(dataList[i])
         
        # print method for debugging
        #for i in range(len(clusterPoints)):
            #print(str(len(clusterPoints[i])))

        return clusterPoints

    def signalCluster(self, newFreq, newDB):
        """
        Clusters the detected frequencies into signals.  
        Uses frequency and signal strength as detection features

        Args:
            newFreq (list): list of newly detected frequencies
            newDB (list): list of dBm associated with new frequencies
        """

        # pair freqs and dB lists
        #tempList = []

        #for i in range(len(newFreq)):
        #    tempList.append([newFreq[i], newDB[i]])

        #self.dataList.append(tempList)
        self.dataList.append(newFreq)
        self.dbList.append(newDB)

        if len(self.dataList) > self.clusterHistory:
            self.dataList.pop(0)
            self.dbList.pop(0)

        extendedData = []
        #for data in self.dataList:
        #    extendedData.extend(data)
        for i in range(len(self.dataList)):
            for j in range(len(self.dataList[i])):
                # data should look like [frequency, history row]
                extendedData.append([self.dataList[i][j] / 1000000, self.dbList[i][j], i]) # convert to MHz to stop knee calc from going crazy
                #extendedData.append([self.dataList[i][j] / 1000000, i]) # convert to MHz to stop knee calc from going crazy

        if len(extendedData) > 12:
            clusteredData = self.__clusterData(extendedData)
            #print(f"Clusters: {str(len(clusteredData))}")
            
            # extract signal data from the cluster
            signalList = []
            for cluster in clusteredData:
                freq = []
                bw = []
                counterSet = set()
                for i in range(len(cluster)):
                    freq.append(cluster[i][0])
                    bw.append(cluster[i][1])
                    counterSet.add(cluster[i][2])

                if len(freq) > 0:
                    centerFreq = sum(freq) / len(freq)
                else:
                    centerFreq = 0
                
                bandWidth = max(freq) - min(freq)
                
                if max(counterSet) > 0:
                    continuous =  (len(counterSet) / max(counterSet)) * 100
                else:
                    continuous =  0
                powerDiff = max(bw) - min(bw)

                signalList.append([centerFreq, bandWidth, continuous, powerDiff])
                #print(f"{str(round(centerFreq))} : {str(round(bandWidth))}")

            self.__publishSignal(signalList)

            #sorted(signalList, key=lambda x: x[0])
            #for signal in signalList:
                #print(f"{str(round(signal[0]))} : {str(round(signal[1]))} : {str(round(signal[2]))} : {str(round(signal[3]))}")
    
    def sweepFrequencies(self):
        ''' spawns the hackrf_sweep process and then acts on its output '''

        self.bigSweep = subprocess.Popen(["hackrf_sweep", f"-g {str(self.vgaGain)}", f"-l {str(self.lnaGain)}", f"-a {str(self.ampEnable)}", f"-f {str(self.minFreq)}:{str(self.maxFreq)}", f"-w {str(self.binSize)}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        #self.bigSweep = subprocess.Popen(["hackrf_sweep", "-f 1:6000", "-w 1000000"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

        startFreq = str(self.minFreq * 1000000) # minFreq is in MHz, but output is in Hz

        # temp values
        temp50floor = float(0)
        counter50percent = 0
        temp25floor = float(0)
        counter25percent = 0
        temp12floor = float(0)
        counter12percent = 0

        floor50percent = float(-50)
        floor25percent = float(-40)
        floor12percent = float(-30)

        # temp variables for high power stuff
        tempFreq = []
        tempDBM = []
        

        while True:
            #try:
            splitStr = self.bigSweep.stdout.readline().split(", ")
            #print(str(splitStr))

            if len(splitStr) >= 11: # reading a data string

                temp50floor = temp50floor + float(splitStr[6]) + float(splitStr[7]) + float(splitStr[8]) + float(splitStr[9]) + float(splitStr[10])
                counter50percent = counter50percent + 5

                if splitStr[2] == startFreq: # check if a loop has finished

                    # update noise floor
                    if counter50percent > 0: # small edge case that counter is 0
                        floor50percent = (temp50floor / counter50percent)
                    if counter25percent > 0: # small edge case that counter is 0
                        floor25percent = (temp25floor / counter25percent)
                    if counter12percent > 0: # small edge case that counter is 0
                        floor12percent = (temp12floor / counter12percent) + self.dbmAdjust

                    # spawn cluster thread
                    Thread(target=self.signalCluster, args=(tempFreq, tempDBM), daemon=False).start()
                    
                    self.__publishScan(freqList=tempFreq, dbList=tempDBM)

                    # display info for debugging
                    #localTime = time.asctime(time.localtime(time.time()))
                    #print(f"\nLoop completed at: {str(localTime)}")
                    #print(f"New 50% floor: {str(floor50percent)}")
                    #print(f"New 25% floor: {str(floor25percent)}")
                    #print(f"New 12% floor: {str(floor12percent)}")
                    #print(f"Total High Power Targets: {str(len(tempFreq))}")

                    # Reset temp variables
                    counter50percent = float(0)
                    temp50floor = float(0)
                    temp25floor = float(0)
                    counter25percent = 0
                    tempFreq = []
                    tempDBM = []
             
                if float(splitStr[6]) > floor50percent: # First frequency is worth checking out
                    # update 25% Counter
                    temp25floor = temp25floor + float(splitStr[6])
                    counter25percent = counter25percent + 1

                    if float(splitStr[6]) > floor25percent: # First frequency is worth checking out for HighPwr
                        # update 12% Counter
                        temp12floor = temp12floor + float(splitStr[6])
                        counter12percent = counter12percent + 1

                        if float(splitStr[6]) > floor12percent: # First frequency is a target
                            tempFreq.append(int(splitStr[2]) + (0 * round(float(splitStr[4]))))
                            tempDBM.append(float(splitStr[6]))

                if float(splitStr[7]) > floor50percent: # Second frequency is worth checking out
                    # update 25% Counter
                    temp25floor = temp25floor + float(splitStr[7])
                    counter25percent = counter25percent + 1

                    if float(splitStr[7]) > floor25percent: # Second frequency is worth checking out for HighPwr
                        # update 12% Counter
                        temp12floor = temp12floor + float(splitStr[7])
                        counter12percent = counter12percent + 1

                        if float(splitStr[7]) > floor12percent: # Second frequency is a target
                            tempFreq.append(int(splitStr[2]) + (1 * round(float(splitStr[4]))))
                            tempDBM.append(float(splitStr[7]))

                if float(splitStr[8]) > floor50percent: # Third frequency is worth checking out
                    # update 25% Counter
                    temp25floor = temp25floor + float(splitStr[8])
                    counter25percent = counter25percent + 1

                    if float(splitStr[8]) > floor25percent: # Third frequency is worth checking out for HighPwr
                        # update 12% Counter
                        temp12floor = temp12floor + float(splitStr[8])
                        counter12percent = counter12percent + 1

                        if float(splitStr[8]) > floor12percent: # Third frequency is a target
                            tempFreq.append(int(splitStr[2]) + (2 * round(float(splitStr[4]))))
                            tempDBM.append(float(splitStr[8]))

                if float(splitStr[9]) > floor50percent: # Fourth frequency is worth checking out
                    # update 25% Counter
                    temp25floor = temp25floor + float(splitStr[9])
                    counter25percent = counter25percent + 1

                    if float(splitStr[9]) > floor25percent: # Fourth frequency is worth checking out for HighPwr
                        # update 12% Counter
                        temp12floor = temp12floor + float(splitStr[9])
                        counter12percent = counter12percent + 1

                        if float(splitStr[9]) > floor12percent: # Fourth frequency is a target
                            tempFreq.append(int(splitStr[2]) + (3 * round(float(splitStr[4]))))
                            tempDBM.append(float(splitStr[9]))

                if float(splitStr[10]) > floor50percent: # Fifth frequency is worth checking out
                    # update 25% Counter
                    temp25floor = temp25floor + float(splitStr[10])
                    counter25percent = counter25percent + 1

                    if float(splitStr[10]) > floor25percent: # Fifth frequency is worth checking out for HighPwr
                        # update 12% Counter
                        temp12floor = temp12floor + float(splitStr[10])
                        counter12percent = counter12percent + 1

                        if float(splitStr[10]) > floor12percent: # Fifth frequency is a target
                            tempFreq.append(int(splitStr[2]) + (4 * round(float(splitStr[4]))))
                            tempDBM.append(float(splitStr[10]))                 
                
            else:
                print("Something went wrong with splitting bigSweep response")
                print(str(splitStr))
                self.bigSweep.kill()
                self.connection.close()
                sys.exit()

    def startSweeper(self):
        ''' spawns all the sweeper threads'''

        self.sweepThread = Thread(target=self.sweepFrequencies, daemon=False)
        self.sweepThread.start()
        
if __name__ == "__main__":

    print("Starting CACTUS")
    sweeper = Cactus(minFreq=400)

    print(f"Beginning Sweeper at {str(time.asctime(time.localtime(time.time())))}")
    sweeper.startSweeper()