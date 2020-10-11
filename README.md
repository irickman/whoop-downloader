# Whoop-downloader
The whoop-downloader script contains a set of wrapper functions to allow you to authenticate and download your WHOOP data.

To get started, clone this repo, then install the required packages. Jupyter is not included, so to use the attached [example workbook](https://github.com/irickman/whoop-downloader/blob/main/Testing%20WHOOP%20Downloader.ipynb), you'll need to install jupyter as well. To ensure you have the correct packages, run the line below. Please note that the script may work without running requirements.txt if you already have these packages and dependencies installed. You may want to use a separate environment to keep your packages synced.

`pip3 install -r requirements.txt`

## Authenticating
The `whoop_downloader` module can be imported and the `whoop_login` class can be used to handle all your data requests. Before you can use the login function to generate an API token and access your WHOOP data, you'll need to set up your .ini file. You can use the [whoop.ini](https://github.com/irickman/whoop-downloader/blob/main/whoop.ini) file to store your credentials. If you don't store your [whoop.ini](https://github.com/irickman/whoop-downloader/blob/main/whoop.ini) file in the same folder as your scripts, you'll want to make sure the location is either in your path or that you provide the full path to your .ini file so the authentication script can access it. Once you've set up your .ini file, you can authenticate and generate an API token.  

To get started, you can use the [Testing WHOOP Downloader.ipynb](https://github.com/irickman/whoop-downloader/blob/main/Testing%20WHOOP%20Downloader.ipynb) as a guide or use the sample code below:

```
from whoop_downloader import whoop_login
client=whoop_login()
client.get_authorization('whoop.ini')
keydata=client.get_keydata_all()
```
## Getting data
The script provides access to a few different sources of data. All data can be accessed from either an "all time" function or a "between timeframes" option. The "all time" functions will pull your data from your first recorded day on WHOOP, while the "between timeframes" function will pull between two specified dates (if no end date is specified, it will default to today).

All of the "get all" functions store their results in an accessible variable, detailed below, so for many of the functions, you'll only need to wait for them to run once. When you run them a second time, the data will be available immediately. As an example, if you run the "get_keydata_all" function, then run the "get_keydata_timeframe" function, it will simply filter the "all_data" dataset to return the result. Please note that this behavior will only work within the same session, with the same variable name. You can also reset this behavior within the session by setting the stored variable = None.

### Key data
The most complete data set you can download is your key data. It contains your daily strain, recovery, sleep, and other metrics. The resulting functions will return data frames where each row is one day. The available functions are:

* **get_keydata_all()** - to access all your key data
* **get_keydata_timeframe(start='YYYY-MM-DD', end="YYYY-MM-DD")** - to access your key data between two dates (if no end date is specified, it will default to today)

**The activities data comes directly out of the key data and the sleep data uses the sleep ids from the Key Data, so I recommend running this method first**, as the other two methods will run it anyways if it hasn't been run. Once you run this method, the data is stored and readily available for use.

Depending on how long you've been on WHOOP, the "get_keydata_all" method may take a bit of time - I've been on WHOOP a little over two years so mine takes a little over a minute.

### Activity data
The activity functions can be used to download detailed activity data. The activity dataset is returned as a list column when the key data function makes its API call. These functions just separate out activity data into their own dedicated dataset. If the Key Data function has not been run, this method will run it first, then return the activity data. The available functions are:

* **get_activities_all()** - to access all your activities
* **get_activities_timeframe(start='YYYY-MM-DD', end="YYYY-MM-DD")** - to access your activities between two dates (if no end date is specified, it will default to today)

### Sleep and sleep events
The sleep and sleep events functions return detailed data on sleep. The key dataset contains sleep ids, then the sleep and sleep events functions use the sleep ids to pull individual data on each night's sleep. Please note, that nap data is not available in this version, except for preceding day's reduced sleep need from naps.

The sleep functions return detailed metrics on sleep, while the sleep events functions return the phase (SWS, REM, Light, Awake, Disturbance, Latency), time in minutes, time bounds, and sleep id for each sleep event. The available functions are below:

* **get_sleep_all()** - to access all your sleep data
* **get_sleep_timeframe(start='YYYY-MM-DD', end="YYYY-MM-DD")** - to access your sleep data between two dates (if no end date is specified, it will default to today)
* **get_sleep_events_all()** - to access all your sleep events data
* **get_sleep_events_timeframe(start='YYYY-MM-DD', end="YYYY-MM-DD")** - to access your sleep event data between two dates (if no end date is specified, it will default to today)

If the "get_keydata_all" method has not yet been run, these methods will run it first, then return sleep data. **Please note that the "get_sleep_events_all" function uses data pulled, but not returned via the "get_sleep_all" function. As such, it's highly recommended that you run the "get_sleep_all" function  before the sleep_events functions**

Depending on how long you've been a WHOOP user, the "all functions" make take some time to run. I've been on WHOOP for a little over 2 years and the "get_sleep_all" function took about 8 minutes for me to run, but was closer to 3 minutes when I initially tested it.

### Heart rate data
This method will return heart rates recorded by WHOOP at every 6 second interval. This method by default returns a list, where each entry is a list of [date, time, and heart rate], but can be used to return a data frame. The available functions are below:

* **get_hr_all()** - to access all your heart rate data measured every 6 seconds
* **get_hr_timeframe(start='YYYY-MM-DD', end="YYYY-MM-DD")** - to access your heart rate data, measured every 6 seconds, between two dates (if no end date is specified, it will default to today)

**This method takes a long time to run**. In testing, it typically ran for 12-15 minutes for me, as a user with over 2 years of WHOOP data. It takes about 6 seconds to pull 1 week of heart rate data and 1 minute to pull 10 weeks.

## Additional methods
In addition to the methods above, by using the whoop_login() class, you can access the stored variables and helper functions for your own use. The methods below are available to you:

* **auth_code** - to return the API token you generated in the get_authorization step
* **whoop_id** - to return your WHOOP athlete id (also available online when you login, in your url string)
* **start_datetime** - to return the date and time your WHOOP started collecting your data
* **all_data** - to easily access your get_keydata_all pull
* **all_activities** - to easily access your activity data pull
* **all_sleep** - to easily access your sleep data pull
* **all_sleep_events** - to easily access your sleep event data pull
* **sport_dict** - to return the WHOOP dictionary of IDs and names for activities available (or not available ;)) in the WHOOP app
* **pull_api** - a handy helper function loaded with your authorization token so you can pull from the WHOOP api yourself, just provide a functional url, you also have the option to toggle between json and a data frame, just set df=True)
* **pull_sleep_main** - a handy helper function to pull the main sleep metrics data for an individual sleep (must provide a sleep id)
* **pull_sleep_events** - a handy helper function to pull the sleep events for an individual sleep (must provide a sleep id)


## Acknowledgements
I put together this module to make it easier for others to download their WHOOP data. I originally built my [Two Years on WHOOP](http://www.irarickman.com/blog/Two-Years-On-WHOOP/) visualization back in June, by using the event listener tab to pull an api token and access the WHOOP api methods detailed above. In developing this module, I had originally used a selenium based authentication method, but then I came across this [unofficial api documentation](https://app.swaggerhub.com/apis/DovOps/whoop-unofficial-api/1.0.1) compiled by [jkreileder](https://gist.github.com/jkreileder). After I found his documentation, I switched to an oauth based authentication function, which made the overall script much simpler. I just want to acknowledge his efforts and thank him for compiling the documentation.
