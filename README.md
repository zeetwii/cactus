![A really crappy logo made in paint](./images/cactus.png)

# CACTUS

## Configurable Autonomous Clustering Tuner and Universal Scanner

 Acrynoms are hard mmkay

## The Basics

Cactus is a tool to help in performing spectrum sweeps and analyzing the RF environment around you.  It's designed as a framework where people can use the output to rapidly tune dedicated RF decoders like wifi and lora.  The advantage that cactus provides is sending out a list of active signals the system is receiving every second.  Cactus also does basic analysis of the signals, report out four basic features: center frequency, bandwidth, digital/analog signal, and AM or FM modulation.  Other modules can then use this output to hone in on signals of interest without needing to scan the spectrum themselves.  An example of this is in a wardriving setup, a wifi scanner can use this output to only scan the channels with active devices as opposed having to stop an listen to each one without knowing ahead of time if anything is active on that frequency.

## Inspiration

Cactus has two main sources of inspiration: the [wifi cactus](https://blog.adafruit.com/2017/08/02/wificactus-when-you-need-to-know-about-hackers-wearablewednesday/) and [sparrow-wifi](https://github.com/ghostop14/sparrow-wifi).  The wifi cactus was a project that stacked a bunch of wifi pineapples on top of each other to try and listen to as many wifi channels at once and log everything.  Sparrow-wifi is a spectrum analysis tool that uses the mobility of drones to modernize wardriving and signal source hunting.  

The wifi cactus presents an interesting problem in signal analysis, how do you look at everything at once?  In this case, the cactus has dedicated receivers for most of the 2.4GHz and 5GHz wifi channels.  This is a very hardware heavy solution, as well as physically heavy.  Sparrow-wifi takes a more lightweight approach to the problem by using software defined radios to rapidly scan the spectrum without logging all the data every read, however their implementation is tailored to wifi spectrums, which makes sense given their name.  The team wanted to combine both the ability to do deep long analysis on specific frequencies that the wifi cactus does with the mobility and rapid scanning of sparrow-wifi while also expanding these techniques to work across the RF spectrum.  Cactus has been the results of this work.  

## The Challenge

The challenge of spectrum monitoring and signal analysis can be summed up as how do you look both left and right at the same time?  If someone is doing broad sweeps across the entire spectrum they cannot look close enough at a signal to decode or discover anything of significance about the signal, but if you tune your radio to listen only to a specific frequency you can decode and demodulate that signal but lose the ability to look at what else is happening in the spectrum.  

The easy answer is to just filter through all the possible frequencies of interest and stop when you see something interesting, however this solution becomes increasingly inefficient as you try and look at more frequencies.  For example, lets use the wifi spectrum: there are 14 channels in the 2.4GHz spectrum, which means one can easily hop from channel to channel and cover all frequencies in this band in only 10 seconds or so.  This means even if moving around, you will more than likely identify all the networks on these channels in a short amount of time.  The math changes when you get to the 5GHz band though, there are over 60 channels in the 5GHz band which means it takes minutes instead of seconds to hop and look across each possible channel.  Now you are in a situation where if moving via a car or drone, its possible if not likely to miss some networks as you move around.  Our answer to the problem is to break the problem down by having a dedicated frequency scanner that creates a list only of signals that have active transmitters on them, dramatically reducing the number of channels a dedicated wifi monitor needs to look at for any given cycle.  

Our solution does require at least two radios, one to look wide and one to look deep, but this solution scales much better than the other, and can easily be adapted and expanded to many situations as we'll show in the modules bellow.  

## The modules

All of the modules talk to each other via [RabbitMQ](https://www.rabbitmq.com/) message queues.  

### Cactus

This is the main module, which performs a wide sweep using a dedicated Software Defined Radio (SDR), and outputs the information from those sweeps into two fanout message queues: the first is a list of the top 6% of the frequency bins with the strongest signal detected, the other is is the output of a clustering algorithm that attempt to recreate these and previous frequency bins into actual signal data, such as center frequency, bandwidth, modulation scheme, ect..

Each sweep takes roughly one second to cover the 1MHz to 6GHz range of the HackRF, allowing for the system to be mounted on a highly mobile platform.  Note using other SDRs may affect this timing as `soapy_power` tends to be slower than `hackrf_sweep`.  

#### Nomenclature

At this point it might be useful to go over a few terms so that people don't get lost in what we are talking about.  

##### Deep Look

When you tune your car radio to a given frequency and begin listening to the audio, this is known as a deep look.  Here your radio and software are focusing only on this narrow part of the spectrum and demodulating the targeted signal.  However the radio is ignoring the rest of the spectrum.  

##### Wide Sweep

This is the opposite of a deep look, where you tune the radio to a wide range of the RF spectrum and rapidly sweep between them.  Commands like `hackrf_sweep` and `soapy_power` are examples of software that turns SDRs into wide sweepers.  It's important to note that the output of these processes are not actually individual frequency data, but rather the average of several frequencies summed together in a bin.  This frequency bin doesn't contain any true signal data, but can be used to make assumptions about the presence and behaviors of the signals within the bin.  
