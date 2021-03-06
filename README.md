# PULSE.MSK.RU BackEnd [Oxenaforda]

## About

PULSE.MSK.RU is a draft of new media: users construct agenda and content through their pesonal actions. 
Social media spreading and geolocation functions allow to get real-time city-buzz. 
Using filtering, clustering, and some ML technics, it's possible to recognize events at the time of occurrence.
Event content is extracted from disparate messages and media objects. Produced news are being classified.

## FAQ [draft]

#### Why Oxenaforda?

\- I decided to mark major versions with ancient cities names. Oxenaforda stands for Oxford. And Oxford was selected because of this paper: [Editorial Algorithms: Using Social Media to Discover and Report Local News](http://www.aaai.org/ocs/index.php/ICWSM/ICWSM15/paper/view/10593)

## Change Log

### [Unreleased]

#### TBD:

- Multi-document text summarisation tool for event.

- New streams for collector: messages "success" level monitoring, engagement stats for selected posts.

#### Added:

- Telegram bot: currently both UI and administrative backend part;

- EventLight() class - class for event representation, minimized version, without classifier/graps/etc;

- Separate SQL table for reference datapoints, updated daily;

#### Changed:

- event_trainer SQL table now stores raw events, not features for classifier, so new features could be easily introduced;

- Event detector now utilizes number of neighbour messages metric, not average distance;

- Once a day detector updates refernce data table, and rebuilds classifier, including recently verified events;

- Jaccard index (0.3 by default) is used for event successors detection;

#### Fixed:

- Infinite events with thousands of messages;

- Memory consumption decreased, tokenizer and stemmer are now initialized in Detector, and are inherited by Events, and not initialized in every Event independently;

### [v1.0.1 event classifier] - 2016-01-27

#### Added:

- settings_template.py with comments;

- emulator.py - separate file for CollectorEmulator with commandline tools;

- Bounds could be specified using .geojson file. And Collectors could filter points: do they exist inside bounds or not;

- Event classifier (decision tree or ada boost) to determine real events;

#### Changed:

- Event class: separate file (event.py); new properties (created, updated, start, end); new methods (is_successor, merge, backup, add_slice).

- Collector class: rewritten to accomplish new requirements, UI removed; 

- Collector class: VK messages collector updated from one central point to the grid;

#### Removed:

- Data sources networks one-letter codes deprecated;

### [v1.0.0 Oxenaforda] - 2015-12-25

#### Added:

- CollectorEmulator class: emulator for real-time messages Collector for online clustering testing. Using fast_forward ratio it's possible to adjust the speed.

#### Changed:

- EventDetector class: grid approach for outliers detection deprecated. Instead kNN distance is used (via bunch of KDTrees: so-called KDForest (-_-) ).

#### Fixed:

- Entropy calculations in Event class: groupby from itertools require sorting.

#### Removed:

- All grid-related calcualtions and functions.

## Third-party dependencies:

- NETWORKING: [requests](http://docs.python-requests.org/en/latest/), [TwitterAPI](https://github.com/geduldig/TwitterAPI);

- DATABASES: [redis](https://pypi.python.org/pypi/redis), [PySQLPool](https://pythonhosted.org/PySQLPool/tutorial.html), [MySQLdb](http://mysql-python.sourceforge.net/);

- CALCULUS: [numpy](http://www.numpy.org/), [networkx](https://networkx.github.io/), [sklearn](http://scikit-learn.org/stable/), [scipy](http://www.scipy.org/), [shapely](http://toblerity.org/shapely/);

- NLP: [pymorphy2](https://github.com/kmike/pymorphy2), [nltk](http://www.nltk.org/), [gensim](https://radimrehurek.com/gensim/).

## Files:

- collector.py: contains classes for online data parsing in Instagram, Twitter, and VKontakte. Also has console UI. TBD: remove console UI; rewrite output queues (like in CollectorEmulator); fix bugs;

- detector.py: EventDetector class - infinity loop, looking for messages outliers, using current topology, and merging messages into slices, and slices - into events. TBD: events validator algorithm;

- event.py: Event object - event candidate, produced by EventDetector. Stores all event-related data;

- settings_template.py: settings.py is required file for backend, but it contains sensitive data (SM credentials). This is a template for settings;

- emulator.py: CollectorEmulator class;

- utilities.py: number of separate utilities, used in other parts and classes, without common importing.