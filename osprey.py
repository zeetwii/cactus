# RF analysis script

import subprocess # needed for hackrf sweep
import sys # needed for rabbit
import os # needed for file stuff
import time # needed for sleep
from threading import Thread # needed for threads

import pika # needed for rabbitMQ

from sklearn.cluster import KMeans # needed for clustering
from sklearn.cluster import DBSCAN # needed for DBSCAN clustering
import numpy as np # needed for clustering
from sklearn.neighbors import NearestNeighbors # needed for helping find epsilon
from kneed import KneeLocator # needed for helping to find epsilon

class Osprey:
    """
    Class to handle RF stuff
    """

    def __init__(self, minFreq=1, maxFreq=6000, ampEnable=1, lnaGain=40, vgaGain=30, binSize=100000, dbmAdjust=0, clusterHistory=60):
        """
        Initalization method

        Args:
            minFreq (int, optional): The min frequency to scan in MHz. Defaults to 1.
            maxFreq (int, optional): The max frequency to scan in MHz. Defaults to 6000.
            ampEnable (int, optional): 0 to disable amplifer, anything else to enable. Defaults to 1.
            lnaGain (int, optional): LNA gain (0-40 dB). Defaults to 40.
            vgaGain (int, optional): VGA gain (0-62 dB). Defaults to 40.
            binSize (int, optional): The width of each frequency bin in Hertz. Defaults to 100000.
            dbmAdjust (float, optional): Adds to the calculated power cutoff for minimum dBm to be considered a signal. Defaults to 0.
            clusterHistory (int, optional): The ammount of previous runs to include when clustering, defaults to 60.
        """

        # rabbitMQ setup
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='signalSweep', exchange_type='fanout')
        
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

    def __clusterData(self, dataList):
        """
        Generates clustering data

        Args:
            dataList (list): the list of data points to cluster

        Returns:
            list: list of clustered points
        """

        # gets distance from all neighbours
        neighbors = NearestNeighbors(n_neighbors=11).fit(np.asarray(dataList))
        distances, indices = neighbors.kneighbors(np.asarray(dataList))
        distances = np.sort(distances[:,10], axis=0)

        # find knee point
        knee = KneeLocator(np.arange(len(distances)), distances, S=1, curve='convex', direction='increasing', interp_method='polynomial')
        
        # use knee point to calculate clusters
        dbClusters = DBSCAN(eps=distances[knee.knee], min_samples=8).fit(np.asarray(dataList))

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
        tempList = []

        for i in range(len(newFreq)):
            tempList.append([newFreq[i], newDB[i]])

        self.dataList.append(tempList)
        #print(str(self.dataList))
        #print(str(len(self.dataList)))

        if len(self.dataList) > self.clusterHistory:
            self.dataList.pop(0)

        extendedData = []
        for data in self.dataList:
            extendedData.extend(data)

        if len(extendedData) > 1:
            clusteredData = self.__clusterData(extendedData)
            print(str(len(clusteredData)))

        

    
    def sweepFrequencies(self):
        ''' spawns the hackrf_sweep process and then acts on its output '''

        self.bigSweep = subprocess.Popen(["hackrf_sweep", f"-g {str(self.vgaGain)}", f"-l {str(self.lnaGain)}", f"-a {str(self.ampEnable)}", f"-f {str(self.minFreq)}:{str(self.maxFreq)}", f"-w {str(self.binSize)}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        #self.bigSweep = subprocess.Popen(["hackrf_sweep", "-f 1:6000", "-w 1000000"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

        startFreq = str(self.minFreq * 1000000) # minFreq is in MHz, but output is in Hz

        tempFloor = float(0)
        counter = 0
        tempFreq = []
        tempDBm = []
        noiseFloor = float(-50)

        # temp variables for high power stuff
        tempPowerFloor = float(0)
        counterPwr = 0
        tempPwr = []
        tempDBmPwr = []
        highPowerFloor = float(-40)

        while True:
            #try:
            splitStr = self.bigSweep.stdout.readline().split(", ")
            #print(str(splitStr))

            if len(splitStr) >= 11: # reading a data string

                tempFloor = tempFloor + float(splitStr[6]) + float(splitStr[7]) + float(splitStr[8]) + float(splitStr[9]) + float(splitStr[10])
                counter = counter + 5

                if splitStr[2] == startFreq: # check if a loop has finished

                    # update noise floor
                    if counter > 0: # small edge case that counter is 0
                        noiseFloor = (tempFloor / counter)
                    if counterPwr > 0: # small edge case that counter is 0
                        highPowerFloor = (tempPowerFloor / counterPwr) + self.dbmAdjust

                    # publish list on rabbitMQ TODO: Change this
                    #self.publishLists(tempFreq, tempDBm, tempPwr, tempDBmPwr)

                    # spawn cluster thread
                    Thread(target=self.signalCluster, args=(tempPwr, tempDBmPwr), daemon=False).start()
                    
                    # display info for debugging
                    localTime = time.asctime(time.localtime(time.time()))
                    print("\nLoop completed at: " + localTime)
                    print("New noise floor: " + str(noiseFloor))
                    print(f"Total Targets: {len(tempFreq)}")
                    print(f"New high power floor: {str(highPowerFloor)}")
                    print(f"Total High Power Targets: {str(len(tempPwr))}")

                    # Reset temp variables
                    counter = float(0)
                    tempFloor = float(0)
                    tempFreq = []
                    tempDBm = []

                    tempPowerFloor = float(0)
                    counterPwr = 0
                    tempPwr = []
                    tempDBmPwr = []
             
                if float(splitStr[6]) > noiseFloor: # First freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (0 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[6]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[6])
                    counterPwr = counterPwr + 1

                    if float(splitStr[6]) > highPowerFloor: # First freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (0 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[6]))
                if float(splitStr[7]) > noiseFloor: # Second freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (1 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[7]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[7])
                    counterPwr = counterPwr + 1

                    if float(splitStr[7]) > highPowerFloor: # Second freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (1 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[7]))

                if float(splitStr[8]) > noiseFloor: # Third freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (2 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[8]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[8])
                    counterPwr = counterPwr + 1

                    if float(splitStr[8]) > highPowerFloor: # First freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (2 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[8]))

                if float(splitStr[9]) > noiseFloor: # Fourth freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (3 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[9]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[9])
                    counterPwr = counterPwr + 1

                    if float(splitStr[9]) > highPowerFloor: # Fourth freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (3 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[9]))

                if float(splitStr[10]) > noiseFloor: # Fifth freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (4 * round(float(splitStr[4]))))   
                    tempDBm.append(float(splitStr[10]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[10])
                    counterPwr = counterPwr + 1

                    if float(splitStr[10]) > highPowerFloor: # Fifth freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (4 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[10]))                 
                
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

    sweeper = Osprey()

    sweeper.startSweeper()