
- [Overview](#overview)
  - [FluBot malware](#flubot-malware)
  - [Proposed method](#proposed-method)
  - [DoH traffic classification](#doh-traffic-classification)
  - [Infected network traffic
    recording](#infected-network-traffic-recording)
  - [Model training](#model-training)
  - [Malware detection](#malware-detection)
- [Design and log of experiment 1](#sec-experiment-design)
  - [OpenWRT router configuration](#openwrt-router-configuration)
  - [Infection of Android with
    FluBot](#infection-of-android-with-flubot)
  - [Generate benign traffic](#generate-benign-traffic)
  - [Record traffic](#record-traffic)
- [Experiment](#sec-experiment-log)
  - [Log](#log)
  - [Artifacts](#artifacts)
- [Training models](#sec-training)
  - [Training data](#training-data)
  - [Training process overview](#training-process-overview)
  - [Data preparation diagrams](#data-preparation-diagrams)
  - [Hyperparameters selection](#hyperparameters-selection)
- [Malware detection overview](#sec-detection-overview)
  - [Concept drift: Train the scaler on production data](#sec-scaler)
  - [Model deployment](#model-deployment)
  - [DoH exfiltration detection
    algorithm](#doh-exfiltration-detection-algorithm)
- [Design and log of experiment 2](#design-and-log-of-experiment-2)
  - [Network setup](#network-setup)
  - [Experiment plan](#experiment-plan)
  - [Log](#log-1)
  - [Artifacts](#artifacts-1)
- [Results](#results)
  - [DNS-over-HTTPS detection model training
    results](#dns-over-https-detection-model-training-results)
  - [Flubot detection “Clean room” experiment 1
    results](#flubot-detection-clean-room-experiment-1-results)
    - [Baseline models](#baseline-models)
    - [Best unnormed and normed
      models](#best-unnormed-and-normed-models)
  - [Flubot detection “Real-world” experiment 2
    results](#flubot-detection-real-world-experiment-2-results)
- [References](#references)

# Overview

In this experiment we are analyzing the proposed method of detection
DNS-over-HTTPS Exfiltration traffic.

## FluBot malware

We are using the sample of FluBot malware - Android malware which
performs exfiltration of data using DoH, ([Figure 1](#fig-flubot)). It
was active during 2021 and 2022, in the

Sample of FluBot 5.2 was downloaded from the
[vx-underground](https://samples.vx-underground.org/samples/Families/Android.FluBot/Samples/5.2/4859ab9cd5efbe0d4f63799126110d744a42eff057fa22ff1bd11cb59b49608c.7z).
In the version 5.0 DoH tunneling feature was integrated to the FluBot.

In the May 2022 the FluBot infrastracture was taken down by then
[EuroPol](https://www.europol.europa.eu/media-press/newsroom/news/takedown-of-sms-based-flubot-spyware-infecting-android-phones).
However, we use it as a real-world malware sample to validate the DoH
tunneling/exfiltration detection algorithm.

Report of F5.com on the FluBot malware can be found
[here](./F5-FluBot.pdf).

<img src="src/imgs/flubot-masks-as-flash-player.png" id="fig-flubot"
class="quarto-discovered-preview-image"
alt="Figure 1: Flubot masks as a flash player" />

## Proposed method

The proposed method is based on the two steps:

- Classify network flows as a DoH or non-DoH, with a classifier built on
  the @Jerabek2022Collection dataset
  (<https://zenodo.org/record/6024914#.ZAcru-xBzaV>)
- Apply the Netflow-based DGA detection algorithm @Grill2015 to detect
  infected machines

Machine-learning classification of DoH traffic allows us to apply the
algorithm to DoH traffic, originally designed for the plaintext DNS.

## DoH traffic classification

DoH traffic uses using standard HTTPS 443 port, which blends DNS packets
within the generic HTTPS traffic. Netflow/IPFIX data of the DoH traffic
does not contain direct features which could help to distinguish DNS
traffic from other HTTPS communications. In this experiment we build a
classifier on the @Jerabek2022Collection dataset using Logistic
Regression, Random Forest and the Histogram-based Gradient Boosting
(**?@sec-build-models**), and selecting the models which are the most
robust to the different network environment (**?@sec-robustness**).

## Infected network traffic recording

For the experiment, we modelled the malware detection algorithm
deployment into the production network. For that we deployed the sandbox
network environment into the Proxmox server with 4 machines: 3 Android
x86 emulators and 1 Kali Linux instance (see
[Section 2](#sec-experiment-design)), behind the OpenWRT router
provisioned with the `IPFIXprobe` tool for recording traffic on the
network border.

One of the Android machines was infected by the FluBot malware during
the experiment, the traffic was collected and saved to the CSV files
(see [Section 3](#sec-experiment-log))
[Figure 2](#fig-capture-screenshot) .

<img src="src/imgs/exp1-screen2.png" id="fig-capture-screenshot"
alt="Figure 2: Screenshot" />

## Model training

Model training includes data preparation in two steps (cached processing
and preprocessing with hyperparameters) (see
[Section 4](#sec-training)).

<img src="src/imgs/overview.png" id="fig-training-overview"
alt="Figure 3: Model training overview" />

## Malware detection

To detect the malicious behavior of the machine, we propose to use the
ratio of DNS requests and contacted IP addresses for every host in the
local network described in the @Grill2015. The paper was focused on
DGA-based malware detection. However, the approach should be used to
detect DNS data exfiltration, too, since the behavior pattern is similar
(see [Section 5](#sec-detection-overview)).

<img src="src/imgs/detection.png" id="fig-detection-overview"
alt="Figure 4: Malware detection overview" />

# Design and log of experiment 1

Sandbox network layout ([Figure 5](#fig-network)):

- 3 Android nodes
- Linux machine with installed `adb` to install malware and control
  Android browser
- OpenWRT router with running tcpdump

Android nodes:

- 192.168.2.149 Android with Chrome configuted **with DoH**
- 192.168.2.249 Android with Chrome configured for **plaintext DNS**
- 192.168.217 Android to be infected with FluBot

<img src="src/imgs/network.drawio.png" id="fig-network"
alt="Figure 5: Network" />

## OpenWRT router configuration

OpenWrt is provided with IPFIXprobe package installed from
https://github.com/CESNET/Nemea-OpenWRT with

- pcap support
- NEMEA unirec support
- `pstats` plugin collects 100 first packets (30 by default)
  `PSTATS_MAXELEMCOUNT` = 100:
  `process/pstats.hpp:# define PSTATS_MAXELEMCOUNT 100`

## Infection of Android with FluBot

We install flubot to 192.168.2.217 Android using sample from
[vx-underground](https://samples.vx-underground.org/samples/Families/Android.FluBot/Samples/5.2/4859ab9cd5efbe0d4f63799126110d744a42eff057fa22ff1bd11cb59b49608c.7z).

`infect.sh`:

``` bash
```

Then we need to allow “Flash Player” (flubot) permission for
accessibility services and machine is infected.

## Generate benign traffic

On 192.168.2.149 and 192.168.2.249 machines we generate benign traffic.
Both ot them are going to browse top 500 domains from the
[moz.com](https://moz.com/top-500/download?table=top500Domains).

To do that, we install the latest Chrome (\>=83 with DoH support).
[Chrome
111](https://www.apkmirror.com/apk/google-inc/chrome/chrome-111-0-5563-49-release/google-chrome-fast-secure-111-0-5563-49-9-android-apk-download/).

On 192.168.2.149 we configure DoH (see [Figure 6](#fig-chrome-doh)).

<img src="src/imgs/android-chrome-doh.png" id="fig-chrome-doh"
alt="Figure 6: Chrome configured to use DoH" />

Chrome installation:

    adb shell settings put global verifier_verify_adb_installs 0
    adb install chrome.apk

Script `traffic.py` (**?@sec-scripts**) randomly navigates both machines
to different websites from the top 500 list. Once in a while it changes
the DoH provider on the 192.168.2.149 machine from the predefined list:

- https://dns.google/dns-query
- https://cloudflare-dns.com/dns-query
- https://dns.quad9.net/dns-query
- https://unfiltered.adguard-dns.com/dns-query
- https://doh.cleanbrowsing.org/doh/security-filter/
- https://freedns.controld.com/p0

## Record traffic

1.  Start all instances [Figure 2](#fig-capture-screenshot):
2.  Start `ipfixprobe` on `exp-outer-router.local`:

`probe.sh`:

``` bash
```

3.  Start logger (IPFIX collector from the `ipfixprobe`) `conda.local`:

`logger.sh`:

``` bash
```

Captured traffic is saved to the CSV file using the `logger` tool from
the NEMEA framework [Figure 7](#fig-capture).

<img src="src/imgs/capture.png" id="fig-capture"
alt="Figure 7: Capture" />

# Experiment

Experiment is conducted in two parts (see [Figure 8](#fig-timeline)):

<img src="src/imgs/timeline.png" id="fig-timeline"
alt="Figure 8: Timeline" />

- B1: We collect a sample of traffic from the monitored network to train
  the scaler (see [Section 5.1](#sec-scaler))
- B2: We collect benign (A1) and infected (A2) traffic to validate the
  malware detector

## Log

| Timestamp  | Time from start (minutes) | Duration | Log                                                 | Save                    |
|------------|---------------------------|----------|-----------------------------------------------------|-------------------------|
| 4:07:16 PM | 0                         |          | Start data collection (ipfixprobe and logger)       |                         |
| 4:08:00 PM | 1                         | 1        | Started traffic.py                                  |                         |
| 4:49:21 PM | 42                        | 41       | Stop data collection                                | save result to v5_1.csv |
| 4:50:21 PM | 43                        | 1        | Start data collection again (ipfixprobe and logger) |                         |
| 5:50:22 PM | 103                       | 60       | Started infect.sh                                   |                         |
| 6:50:31 PM | 163                       | 60       | Stop data collection                                | save result to v5_2.csv |

## Artifacts

- B1 part of traffic saved into `v5_1.csv`
- B2 part of traffic saved into `v5_2.csv`
- `traffic.py` log is saved in `v5_exp.log`
- High-level log with timestamps of experiment is saved in `v5_log.csv`

# Training models

## Training data

Model training is done on the DoH traffic collection described in
@Jerabek2022Collection

- <https://zenodo.org/record/6024914#.ZAcru-xBzaV>

This dataset contains a large collection of generated DoH data from
Chrome and Firefox browsers using GET and POST methods on multiple DoH
public resolvers.

## Training process overview

Models training is done in the following steps:

- Cacheable processing
  - Filter HTTPS traffic
  - Parse packet lengths and timestamps array fields
  - Split packet lengths and timestamps arrays by outgoing and incoming
    directions
  - Calculate inter-packet duration from the timesamps
  - Label flows (boolean IsDoH field)
- PreProcessing
  - Calculate stats (mean, variance, stddev) on
    - Packet lengths (all, incoming, outgoing)
    - Inter-packet duration (all, incoming, outgoing)
  - Normalization of the feature fields
  - Split features and label columns

Feature fields (1 and -1 represent outgoing and incoming packets
respectively):

- uint16\* PPI_PKT_LENGTHS_stddev
- uint16\* PPI_PKT_LENGTHS_mean
- uint16\* PPI_PKT_LENGTHS_var
- uint16\* PPI_PKT_LENGTHS_1_stddev
- uint16\* PPI_PKT_LENGTHS_1_mean
- uint16\* PPI_PKT_LENGTHS_1_var
- uint16\* PPI_PKT_LENGTHS\_-1_stddev
- uint16\* PPI_PKT_LENGTHS\_-1_mean
- uint16\* PPI_PKT_LENGTHS\_-1_var
- PPI_PKT_INTERVALS_stddev
- PPI_PKT_INTERVALS_mean
- PPI_PKT_INTERVALS_var
- PPI_PKT_INTERVALS_1_stddev
- PPI_PKT_INTERVALS_1_mean
- PPI_PKT_INTERVALS_1_var
- PPI_PKT_INTERVALS-1_stddev
- PPI_PKT_INTERVALS-1_mean
- PPI_PKT_INTERVALS-1_var

## Data preparation diagrams

Data preparation is done in two steps: - Cacheable processing
(non-parametric processing) [Figure 9](#fig-cp) - Preprocessing (applies
hyperparameters) [Figure 10](#fig-pp)

<img src="src/imgs/cp.png" id="fig-cp"
alt="Figure 9: Cachable processing" />

<img src="src/imgs/pp.png" id="fig-pp" alt="Figure 10: Preprocessing" />

## Hyperparameters selection

1.  Normalization

The hypothesis is that the normalization of statistical features
separately on training and test (production) set will allow us reduce
the concept drift in case these datasets were recorded in different
networks (see [Section 5.1](#sec-scaler)).

2.  Skip first packets

(TODO: reference)

Skipping first few packets should reduce the importrance of TLS
handshake which may be very similar for DoH and non-DoH HTTPS traffic,
and focus the detection on the traffic content.

Other technique which is tested in this experiment is applying weights
on the features, instead of just skipping them (in this case skipping
the packet equal to 0.0 weight).

Weight for N packets is calculated linearly increasing:

- from $0.1$ for the 1 packet
- to $1.0$ for N+1’s packet.

For example, for skip=1, weight=2 and length of packets array=7 the
weights will be the following:

| id     | 1    | 2      | 3      | 4   | 5   | 6   | 7   |
|--------|------|--------|--------|-----|-----|-----|-----|
| action | skip | weight | weight | \-  | \-  | \-  | \-  |
| weight | 0\.  | 0.1    | 0.55   | 1\. | 1\. | 1\. | 1\. |

Then we calculate the weighted mean, weighted variance and weighted
standard deviation for the features:

- All packet lengths: `uint16* PPI_PKT_LENGTHS`
- Outgoing packet lengths: `uint16* PPI_PKT_LENGTHS_1`
- Incoming packet lengths: `uint16* PPI_PKT_LENGTHS_-1`
- All inter-packet durations: `PPI_PKT_INTERVALS`
- Outgoing inter-packet durations: `PPI_PKT_INTERVALS_1`
- Incoming inter-packet durations: `PPI_PKT_INTERVALS-1`

This way we have following hyperparameters represented as a tuple of
(norm, A, B, C, D):

- normalization (on/off)
- skip A first packets for inter-packet duration statistics
- skip B first packets for packet sizes statistics
- apply weight on C first packets for inter-packet duration statistics
- apply weight on D first packets for sizes statistics

# Malware detection overview

## Concept drift: Train the scaler on production data

The network environment used to collect the training dataset and the one
in which model will run in production will most likely be different:
collection of a large labeled dataset require special configuration and
usually done in a sandbox network separate from the real world traffic.
This difference includes interferes with inter-packet duration
measurements, packet routes and other features that we call generally
“concept drift”.

In this experiment we train (fit) the scaler on the training data and on
test data separately, it means that the scaling ranges and percentiles
used to scale the production data are differ from the ones used in the
training dataset. The hypothesis is that separate scaling training may
help to reduce the concept drift introduced by a different network.

## Model deployment

On this stage we already have the model, or rather a group of models (3
unnormed and 3 normed) which perform the best on the test data. Before
we can deploy the model to the production to perform DoH detection, we
should train the scaler on the new network. For that, we collect the
traffic for the period of time (B1) on the timeline, without doing any
inference [Figure 8](#fig-timeline), and train the scaler on this data.
In the second period (B2) we can start the malware detection module with
model and the trained scaler (see [Figure 11](#fig-model-deployment)).

<img src="src/imgs/model-deployment.png" id="fig-model-deployment"
alt="Figure 11: Model deployment" />

## DoH exfiltration detection algorithm

To detect the malicious behavior of the machine, we propose to use the
ratio of DNS requests and contacted IP addresses for every host in the
local network described in the @Grill2015:

$$\rho(a)={\delta(a) \over \pi(a) + 1}$$

- $a$ is the host in the network
- $\delta(a)$ values - number of DNS requests created by the host `a`
- $\pi(a)$ values - the number of unique IP addresses contacted by the
  `a`

The value of the ratio $\rho(a)$ represents the “specific gravity” of
contacted IP addresses per DNS request and can be used to detect DGA-,
fast-fluxing-based malware, DNS Tunneling, and exfiltration attacks.

The overall number of DNS requests $\delta(a)$ is linearly dependent on
the observed duration, while the rate of increase of the count of new
IPs in the time window is logarithmically decreases over time. To make
the detection algorithm more robust to the change of the observed time
window, we use $log(\rho)$ in our experiments.

# Design and log of experiment 2

First experiment (see [Section 2](#sec-experiment-design)) was a “clean
room” experiment, with an infected machine without benign traffic, and
two control machines with benign traffic only.

In second experiment we conduct a real-world scenario where a machine
which is used to browse internet and generate benign traffic is being
infected, and generate a “mixed” benign and malicious traffic.

For this experiment we use modified `traffic.py` - `traffic2.py`. Main
differences:

- No change of DoH resolvers, they are selected on the beginning of the
  experiment
- No DNS cache clearing each 10 requests, to make it closer to
  real-world browsing: frequent cache clearing artificially increases
  the `\rho(a)` value.

## Network setup

We configured 2 Android x86 machines:

- 192.168.2.217 - machine with mixed traffic, benign in A1 period;
  benign and infected with FluBot in A2 period (see
  [Figure 8](#fig-timeline))
- 192.168.2.149 - clean machine with DoH in Chrome enabled

Also, same as in the first experiment, we have:

- OpenWRT router of sandbox network with IPFIXprobe running
- Linux machine inside the sandbox network, which is used to control
  Android machines via ADB shell
- Linux machine outside of the network which is used to collect traffic
  from IPFIXprobe and convert it to CSV

## Experiment plan

We conduct an experiment with the plan similar to the first one,
collecting data in two (B1 and B2) periods (see
[Figure 8](#fig-timeline)).

![Timeline](src/imgs/timeline.png)

- B1: We collect a sample of traffic from the monitored network to train
  the scaler (see [Section 5.1](#sec-scaler))
- B2: We collect benign (A1) and infected (A2) traffic to validate the
  malware detector

## Log

| Timestamp   | Time from start (minutes) | Duration | Log                                                     |
|-------------|---------------------------|----------|---------------------------------------------------------|
| 11:00:02 AM | 0                         | 0        | B1: Start data collection (ipfixprobe and logger)       |
| 11:00:59 AM | 1                         | 1        | Started traffic2.py                                     |
| 11:17:15 AM | 17                        | 16       | Stop data collection, save result to v7_1.csv           |
| 11:36:11 AM | 36                        | 19       | Stop traffic2.py, save v7_exp_1.log                     |
| 11:44:50 AM | 45                        | 9        | B2: Start data collection again (ipfixprobe and logger) |
| 11:46:00 AM | 46                        | 1        | Started traffic2.py                                     |
| 11:56:59 AM | 57                        | 11       | Started infect.sh                                       |
| 12:14:18 PM | 74                        | 17       | Stop data collection, save result to v7_2.csv           |
| 12:14:31 PM | 74                        | 0        | Stop traffic2.py, save v7_exp_2.log                     |

## Artifacts

- B1 part of traffic saved into `v7_1.csv`
- B2 part of traffic saved into `v7_2.csv`
- `traffic2.py` log is saved in `v7_exp_1.log` and `v7_exp_2.log`
  (before and after infection)
- High-level log with timestamps of experiment is saved in `v7_log.csv`

# Results

## DNS-over-HTTPS detection model training results

We have built a number of models based on different algorithms and
hyperparameters. Models were evaluated on the “robustness”: ability to
detect DoH not only in the same network where training data was
recorded, but on other networks too. The test dataset containing 50%
from the test sample of training data, and 50% from the recorded traffic
from sandbox network. ROCs of these models are in **?@fig-models-roc**.

<div notebook="notebooks/choose-model.ipynb"
notebook-title="Choose model">

<img src="src/text_files/figure-commonmark/fig-models-roc-output-1.png"
id="fig-models-roc-1" alt="Figure 12: Logistic Regression" />

<img src="src/text_files/figure-commonmark/fig-models-roc-output-2.png"
id="fig-models-roc-2" alt="Figure 13: Hist Gradient Boosting" />

<img src="src/text_files/figure-commonmark/fig-models-roc-output-3.png"
id="fig-models-roc-3" alt="Figure 14: Random Forest" />

ROC and their AUC for test dataset

</div>

Top 3 models with normalization based on their AUC:

<div notebook="notebooks/choose-model.ipynb"
notebook-title="Choose model">

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }
&#10;    .dataframe tbody tr th {
        vertical-align: top;
    }
&#10;    .dataframe thead th {
        text-align: right;
    }
</style>

|     | model | normed | skips_and_weights | test_data_auc | fpr                                                | tpr                                                | thresholds                                         |
|-----|-------|--------|-------------------|---------------|----------------------------------------------------|----------------------------------------------------|----------------------------------------------------|
| 23  | RF    | True   | \[2, 4, 0, 0\]    | 0.9355        | \[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.00010794... | \[0.0, 0.00010486577181208053, 0.00031459731543... | \[1.98, 0.98, 0.97, 0.96, 0.95, 0.94, 0.92, 0.9... |
| 44  | RF    | True   | \[2, 4, 2, 4\]    | 0.9324        | \[0.0, 0.0, 0.0, 0.0, 0.0, 0.000107944732297063... | \[0.0, 0.00041946308724832214, 0.00094379194630... | \[2.0, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94,... |
| 5   | RF    | True   | \[1, 0, 0, 0\]    | 0.9278        | \[0.0, 0.0, 0.0, 0.0, 0.0001079447322970639, 0.... | \[0.0, 0.00010486577181208053, 0.00020973154362... | \[2.0, 1.0, 0.99, 0.98, 0.97, 0.95, 0.93, 0.92,... |

</div>

</div>

Top 3 models without normalization based on their AUC:

<div notebook="notebooks/choose-model.ipynb"
notebook-title="Choose model">

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }
&#10;    .dataframe tbody tr th {
        vertical-align: top;
    }
&#10;    .dataframe thead th {
        text-align: right;
    }
</style>

|     | model | normed | skips_and_weights | test_data_auc | fpr                                                | tpr                                                | thresholds                                         |
|-----|-------|--------|-------------------|---------------|----------------------------------------------------|----------------------------------------------------|----------------------------------------------------|
| 53  | RF    | False  | \[2, 0, 0, 0\]    | 0.9780        | \[0.0, 0.0, 0.0, 0.0001079447322970639, 0.00010... | \[0.0, 0.3485738255033557, 0.3976510067114094, ... | \[2.0, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94,... |
| 68  | RF    | False  | \[2, 4, 0, 0\]    | 0.9761        | \[0.0, 0.0, 0.0, 0.0001079447322970639, 0.00021... | \[0.0, 0.34133808724832215, 0.3921979865771812,... | \[2.0, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94,... |
| 86  | RF    | False  | \[1, 4, 1, 4\]    | 0.9753        | \[0.0, 0.0, 0.0, 0.0002158894645941278, 0.00021... | \[0.0, 0.3493078859060403, 0.39890939597315433,... | \[2.0, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94,... |

</div>

</div>

## Flubot detection “Clean room” experiment 1 results

For this experiment we took 6 models mentioned above, and two models
(normed and unnormed) with hyperparameters equal to \[0,0,0,0\], for the
baseline comparison.

Interestingly, normalized model performed better than the unnormalized,
which aligns with the original hypothesis but doesn’t align with the
training test model comparison.

In the result, normed models with non-0 hyperparameters perform better
or same as the baseline 0-0-0-0 models.

Unnormed models with non-0 hyperparameters perform worse than the
baseline 0-0-0-0 models.

### Baseline models

RF-unnormed-0-0-0-0:

<div notebook="notebooks/flubot-detection-try-models/gen-flubot-detection-RF-unnormed-0-0-0-0.ipynb"
notebook-title="Detect malware (RF unnormed-0-0-0-0)">

    0.8

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-1-output-2.png"
id="fig-rate_log-flubot-exp-1-1-1" alt="Figure 15: sensitivity 0.8" />

    0.9

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-1-output-4.png"
id="fig-rate_log-flubot-exp-1-1-2" alt="Figure 16: sensitivity 0.9" />

$\rho(a)$ plot for all instances (B2 period)

</div>

RF-normed-0-0-0-0:

<div notebook="notebooks/flubot-detection-try-models/gen-flubot-detection-RF-normed-0-0-0-0.ipynb"
notebook-title="Detect malware (RF normed-0-0-0-0)">

    0.8

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-2-output-2.png"
id="fig-rate_log-flubot-exp-1-2-1" alt="Figure 17: sensitivity 0.8" />

    0.9

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-2-output-4.png"
id="fig-rate_log-flubot-exp-1-2-2" alt="Figure 18: sensitivity 0.9" />

$\rho(a)$ plot for all instances (B2 period)

</div>

### Best unnormed and normed models

RF-unnormed-2-0-0-0:

<div notebook="notebooks/flubot-detection-try-models/gen-flubot-detection-RF-unnormed-2-0-0-0.ipynb"
notebook-title="Detect malware (RF unnormed-2-0-0-0)">

    0.8

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-3-output-2.png"
id="fig-rate_log-flubot-exp-1-3-1" alt="Figure 19: sensitivity 0.8" />

    0.9

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-3-output-4.png"
id="fig-rate_log-flubot-exp-1-3-2" alt="Figure 20: sensitivity 0.9" />

$\rho(a)$ plot for all instances (B2 period)

</div>

RF-normed-2-4-0-0:

<div notebook="notebooks/flubot-detection-try-models/gen-flubot-detection-RF-normed-2-4-0-0.ipynb"
notebook-title="Detect malware (RF normed-2-4-0-0)">

    0.8

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-4-output-2.png"
id="fig-rate_log-flubot-exp-1-4-1" alt="Figure 21: sensitivity 0.8" />

    0.9

<img
src="src/text_files/figure-commonmark/fig-rate_log-flubot-exp-1-4-output-4.png"
id="fig-rate_log-flubot-exp-1-4-2" alt="Figure 22: sensitivity 0.9" />

$\rho(a)$ plot for all instances (B2 period)

</div>

## Flubot detection “Real-world” experiment 2 results

In the last experiment we took the model which performed the best on the
first experiment (RF-normed-2-4-0-0) and used to detect the machine
browsing benign websites which is exposed to the FluBot malware at some
point.

ARIMA time-series model was used to learn the hosts normal behavior and
detect outliers (FluBot infection):

<div notebook="notebooks/flubot-detection-second.ipynb"
notebook-title="Detect malware">

    0.8

<img
src="src/text_files/figure-commonmark/fig-real-world-flubot-detection-1-output-2.png"
id="fig-real-world-flubot-detection-1-1"
alt="Figure 23: sensitivity 0.8" />

    0.9

<img
src="src/text_files/figure-commonmark/fig-real-world-flubot-detection-1-output-4.png"
id="fig-real-world-flubot-detection-1-2"
alt="Figure 24: sensitivity 0.9" />

$\rho(a)$ plot for clean and infected instances (B2 period)

</div>

# References


 - Grill, Martin, Ivan Nikolaev, Veronica Valeros, and Martin Rehak. 2015. “Detecting DGA Malware Using NetFlow.” In 2015 IFIP/IEEE International Symposium on Integrated Network Management (IM), 1304–9. https://doi.org/10.1109/INM.2015.7140486.
 - Jeřábek, Kamil, Karel Hynek, Tomáš Čejka, and Ondřej Ryšavý. 2022. “Collection of Datasets with DNS over HTTPS Traffic.” Data in Brief 42 (June): 108310. https://doi.org/10.1016/j.dib.2022.108310.

