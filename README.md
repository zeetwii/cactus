# CACTUS

##### Cyber Autonomus Clustering Tuner and Scanner

###### Finding two words that start with C is hard...

Cactus is a tool to help in performing spectrum sweeps and analyzing the RF environment around you.  It's designed as a framework where people can use the output to rapidly tune dedicated RF decoders like wifi and lora.  The advantage that cactus provides is sending out a list of active signals the system is reciving every second.  Cactus also does basic analysis of the signals, report out four basic features: center frequency, bandwidth, digital/analog signal, and AM or FM modulation.  
## Insperation

Cactus has two main sources of insperation: the [wifi cactus](https://blog.adafruit.com/2017/08/02/wificactus-when-you-need-to-know-about-hackers-wearablewednesday/) and [sparrow-wifi](https://github.com/ghostop14/sparrow-wifi).  The wifi cactus was a project that stacked a bunch of wifi pineapples ontop of eachother to try and listen to as many wifi channels at once and log everything.  Sparrow-wifi is a spectrum analysis tool that uses the mobility of drones to modernize wardriving and signal source hunting.  

The wifi cactus presents an intersting problem in signal analysis, how do you look at everything at once?  In this case, the cactus has dedicated recievers for most of the 2.4GHz and 5GHz wifi channels.  This is a very hardware heavy solution, as well as physically heavy.  Sparrow-wifi takes a more lightweight approch to the problem by using software defined radios to rapidly scan the spectrum without logging all the data every read, however their implementatio is tailored to wifi spectrums, which makes sense given their name.  The team wanted to combine both the ability to do deep long analysis on specific frequencies that the wifi cactus does with the mobility and rapid scanning of sparrow-wifi while also expanding these techniques to work across the RF spectrum.  Cactus has been the results of this work.  

## The Challenge

The challenge of spectrum monitoring and signal analysis can be sumed up as how do you look both left and right at the same time?  If someone is doing broad sweeps across the entire spectrum they cannot look close enough at a signal to decode or discover anything of signifigance about the signal, but if you tune your radio to listen only to a specific frequency you can decode and demodulate that signal but lose the ability to look at what else is happening in the spectrum.  

The easy answer is to just filter through all the possible frequencies of interest and stop when you see something interensting, however this solution becomes increasingly inefficent as you try and look at more frequencies.  For example, lets use the wifi spectrum: there are 14 channels in the 2.4GHz spectrum, which means one can easily hop from channel to channel and cover all frequencies in this band in only 10 seconds or so.  This means even if moving around, you will more than likely identify all the networks on these channels in a short amount of time.  The math changes when you get to the 5GHz band though, there are over 60 channels in the 5GHz band which means it takes minuites instead of seconds to hop and look across each possible channel.  Now you are in a situation where if moving via a car or drone, its possible if not likely to miss some networks as you move around.  Our answer to the problem is to break the problem down by having a dedicated frequency scanner that creates a list only of signals that have active transmitters on them, dramatically reducing the number of channels a dedicated wifi monitor needs to look at for any given cycle.  

Our solution does require at least two radios, one to look wide and one to look deep, but this solution scales much better than the other, and can easily be adapted and expanded to many situations as we'll show in the modules bellow.  
