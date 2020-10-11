import requests
import pandas as pd
import numpy as np
import configparser
from datetime import timedelta, datetime
from dateutil import relativedelta, parser, rrule
from dateutil.rrule import WEEKLY


class whoop_login:
    '''A class object to allow a user to login and store their authorization code,
        then perform pulls using the code in order to access different types of data'''

    def __init__(self, auth_code=None, whoop_id=None,current_datetime=datetime.utcnow()):
        self.auth_code=auth_code
        self.whoop_id=whoop_id
        self.current_datetime=current_datetime
        self.start_datetime=None
        self.all_data=None
        self.all_activities=None
        self.sport_dict=None
        self.all_sleep=None
        self.all_sleep_events=None


    def pull_api(self, url,df=False):
        auth_code=self.auth_code
        headers={'authorization':auth_code}
        pull=requests.get(url,headers=headers)
        if pull.status_code==200 and len(pull.content)>1:
            if df:
                d=pd.json_normalize(pull.json())
                return d
            else:
                return pull.json()
        else:
            return "no response"

    def pull_sleep_main(self,sleep_id):
        athlete_id=self.whoop_id
        sleep=self.pull_api('https://api-7.whoop.com/users/{}/sleeps/{}'.format(athlete_id,sleep_id))
        main_df=pd.json_normalize(sleep)
        return main_df

    def pull_sleep_events(self,sleep_id):
        athlete_id=self.whoop_id
        sleep=self.pull_api('https://api-7.whoop.com/users/{}/sleeps/{}'.format(athlete_id,sleep_id))
        events_df=pd.json_normalize(sleep['events'])
        events_df['id']=sleep_id
        return events_df

    def get_authorization(self,user_ini):
        '''
        Function to get the authorization token and user id.
        This must be completed before a user can query the api
        '''

        config=configparser.ConfigParser()
        config.read(user_ini)
        username=config['whoop']['username']
        password=config['whoop']['password']


        headers={
                "username": username,
                "password": password,
                "grant_type": "password",
                "issueRefresh": False}
        auth = requests.post("https://api-7.whoop.com/oauth/token", json=headers)

        if auth.status_code==200:
            content=auth.json()
            user_id=content['user']['id']
            token=content['access_token']
            start_time=content['user']['profile']['createdAt']
            self.whoop_id=user_id
            self.auth_code='bearer ' + token
            self.start_datetime=start_time
            print("Authentication successful")

        else:
            print("Authentication failed - please double check your credentials")



    def get_keydata_all(self):
        '''
        This function returns a dataframe of WHOOP metrics for each day of WHOOP membership.
        In the resulting dataframe, each day is a row and contains strain, recovery, and sleep information
        '''

        if self.start_datetime:
            if self.all_data is not None:
                ## All data already pulled
                return self.all_data
            else:
                start_date=parser.isoparse(self.start_datetime).replace(tzinfo=None)
                end_time='T23:59:59.999Z'
                start_time='T00:00:00.000Z'
                intervals=rrule.rrule(freq=WEEKLY,interval=1,until=self.current_datetime, dtstart=start_date)
                date_range=[[d.strftime('%Y-%m-%d') + start_time,
                            (d+relativedelta.relativedelta(weeks=1)).strftime('%Y-%m-%d') + end_time] for d in intervals]
                all_data=pd.DataFrame()
                for dates in date_range:
                    cycle_url='https://api-7.whoop.com/users/{}/cycles?end={}&start={}'.format(self.whoop_id,
                                                                                           dates[1],
                                                                                           dates[0])
                    data=self.pull_api(cycle_url,df=True)
                    all_data=pd.concat([all_data,data])
                all_data.reset_index(drop=True,inplace=True)

                ## fixing the day column so it's not a list
                all_data['days']=all_data['days'].map(lambda d: d[0])
                all_data.rename(columns={"days":'day'},inplace=True)

                ## Putting all time into minutes instead of milliseconds
                sleep_cols=['qualityDuration','needBreakdown.baseline','needBreakdown.debt','needBreakdown.naps',
                'needBreakdown.strain','needBreakdown.total']
                for sleep_col in sleep_cols:
                    all_data['sleep.' + sleep_col]=all_data['sleep.' + sleep_col].astype(float).apply(lambda x: np.nan if np.isnan(x) else x/60000)

                ## Making nap variable
                all_data['nap_duration']=all_data['sleep.naps'].apply(lambda x: x[0]['qualityDuration']/60000 if len(x)==1 else(
                                                    sum([y['qualityDuration'] for y in x if y['qualityDuration'] is not None])/60000 if len(x)>1 else 0))
                all_data.drop(['sleep.naps'],axis=1,inplace=True)
                ## dropping duplicates subsetting because of list columns
                all_data.drop_duplicates(subset=['day','sleep.id'],inplace=True)

                self.all_data=all_data
                return all_data
        else:
            print("Please run the authorization function first")

    def get_activities_all(self):
        '''
        Activity data is pulled through the get_keydata functions so if the data pull is present, this function
        just transforms the activity column into a dataframe of activities, where each activity is a row.
        If it has not been pulled, this function runs the key data function then returns the activity dataframe'''

        if self.sport_dict:
            sport_dict=self.sport_dict
        else:
            sports=self.pull_api('https://api-7.whoop.com/sports')
            sport_dict={sport['id']:sport['name'] for sport in sports}
            self.sport_dict=self.sport_dict

        if self.start_datetime:
            ## process activity data

            if self.all_data is not None:
                ## use existing
                data=self.all_data
            else:
                ## pull all data to process activities
                data=self.get_keydata_all()
            ## now process activities data
            act_data=pd.json_normalize(data[data['strain.workouts'].apply(len)>0]['strain.workouts'].apply(lambda x: x[0]))
            act_data[['during.upper','during.lower']]=act_data[['during.upper','during.lower']].apply(pd.to_datetime)
            act_data['total_minutes']=act_data.apply(lambda x: (x['during.upper']-x['during.lower']).total_seconds()/60.0,axis=1)
            for z in range(0,6):
                 act_data['zone{}_minutes'.format(z+1)]=act_data['zones'].apply(lambda x: x[z]/60000.)
            act_data['sport_name']=act_data.sportId.apply(lambda x: sport_dict[x])

            act_data['day']=act_data['during.lower'].dt.strftime('%Y-%m-%d')
            act_data.drop(['zones','during.bounds'],axis=1,inplace=True)
            act_data.drop_duplicates(inplace=True)
            self.all_activities=act_data
            return act_data
        else:
            print("Please run the authorization function first")

    def get_sleep_all(self):
        '''
        This function returns all sleep metrics in a data frame, for the duration of user's WHOOP membership.
        Each row in the data frame represents one night of sleep
        '''
        if self.auth_code:
            if self.all_data is not None:
                ## use existing
                data=self.all_data
            else:
                ## pull timeframe data
                data=self.get_keydata_all()

            ## getting all the sleep ids
            if self.all_sleep is not None:
                ## All sleep data already pulled
                return self.all_sleep
            else:
                sleep_ids=data['sleep.id'].values.tolist()
                sleep_list=[int(x) for x in sleep_ids if pd.isna(x)==False]
                all_sleep=pd.DataFrame()
                for s in sleep_list:
                    m=self.pull_sleep_main(s)
                    all_sleep=pd.concat([all_sleep,m])

                ## Cleaning sleep data
                sleep_update=['qualityDuration','latency','debtPre','debtPost','needFromStrain','sleepNeed',
                              'habitualSleepNeed','timeInBed','lightSleepDuration','slowWaveSleepDuration',
                              'remSleepDuration','wakeDuration','arousalTime','noDataDuration','creditFromNaps',
                              'projectedSleep']

                for col in sleep_update:
                    all_sleep[col]=all_sleep[col].astype(float).apply(lambda x: np.nan if np.isnan(x) else x/60000)

                all_sleep.drop(['during.bounds'],axis=1,inplace=True)
                self.all_sleep=all_sleep.copy(deep=True)
                all_sleep.drop(['events'],axis=1,inplace=True)
                return all_sleep
        else:
            print("Please run the authorization function first")

    def get_sleep_events_all(self):
        '''
        This function returns all sleep events in a data frame, for the duration of user's WHOOP membership.
        Each row in the data frame represents an individual sleep event within an individual night of sleep.
        Sleep events can be joined against the sleep or main datasets by sleep id.
        All sleep times are returned in minutes.
        '''
        if self.auth_code:
            if self.all_data is not None:
                ## use existing
                data=self.all_data
            else:
                ## pull timeframe data
                data=self.get_keydata_all(start,end)

            ## getting all the sleep ids
            if self.all_sleep_events is not None:
                ## All sleep data already pulled
                return self.all_sleep_events
            else:
                if self.all_sleep is not None:
                    sleep_events=self.all_sleep[['activityId','events']]
                    all_sleep_events=pd.concat([pd.concat([pd.json_normalize(events),
                                                            pd.DataFrame({'id':len(events)*[sleep]})],axis=1) for events, sleep in zip(sleep_events['events'],sleep_events['activityId'])])
                else:
                    sleep_ids=data['sleep.id'].values.tolist()
                    sleep_list=[int(x) for x in sleep_ids if pd.isna(x)==False]
                    all_sleep_events=pd.DataFrame()
                    for s in sleep_list:
                        events=self.pull_sleep_events(s)
                        all_sleep_events=pd.concat([all_sleep_events,events])

                ## Cleaning sleep events data
                all_sleep_events['during.lower']=pd.to_datetime(all_sleep_events['during.lower'])
                all_sleep_events['during.upper']=pd.to_datetime(all_sleep_events['during.upper'])
                all_sleep_events.drop(['during.bounds'],axis=1,inplace=True)
                all_sleep_events['total_minutes']=all_sleep_events.apply(lambda x: (x['during.upper']-x['during.lower']).total_seconds()/60.0,axis=1)

                self.all_sleep_events=all_sleep_events
                return all_sleep_events
        else:
            print("Please run the authorization function first")

    def get_hr_all(self,df=False):
        '''
        This function will pull every heart rate measurement recorded for the life of WHOOP membership.
        The default return for this function is a list of lists, where each "row" contains the date, time, and hr value.
        The measurements are spaced out every ~6 seconds on average.

        To return a dataframe, set df=True. This will take a bit longer, but will return a data frame.

        NOTE: This api pull takes about 6 seconds per week of data ... or 1 minutes for 10 weeks of data,
        so be careful when you pull, it may take a while.
        '''
        if self.start_datetime:
            athlete_id=self.whoop_id
            start_date=parser.isoparse(self.start_datetime).replace(tzinfo=None)
            end_time='T23:59:59.999Z'
            start_time='T00:00:00.000Z'
            intervals=rrule.rrule(freq=WEEKLY,interval=1,until=self.current_datetime, dtstart=start_date)
            date_range=[[d.strftime('%Y-%m-%d') + start_time,
                        (d+relativedelta.relativedelta(weeks=1)).strftime('%Y-%m-%d') + end_time] for d in intervals]

            hr_list=[]
            for dates in date_range:
                start=dates[0]
                end=dates[1]
                ul='''https://api-7.whoop.com/users/24590/metrics/heart_rate?end={}&order=t&start={}&step=6'''.format(end,start)
                hr_vals=self.pull_api(ul)['values']
                hr_values=[[datetime.utcfromtimestamp(h['time']/1e3).date(),
                                  datetime.utcfromtimestamp(h['time']/1e3).time(),
                                  h['data']] for h in hr_vals]
                hr_list.extend(hr_values)
            if df:
                hr_df=pd.DataFrame(hr_list)
                hr_df.columns=['date','time','hr']
                return hr_df
            else:
                return hr_list
        else:
            print("Please run the authorization function first")

    def get_keydata_timeframe(self,start,end=datetime.strftime(datetime.utcnow(),"%Y-%m-%d")):
        '''
        This function returns a dataframe of WHOOP metrics for each day in a specified time period.
        To use this function, provide a start and end date in string format as follows "YYYY-MM-DD".

        If no end date is specified, it will default to today's date.

        In the resulting dataframe, each day is a row and contains strain, recovery, and sleep information
        '''

        st=datetime.strptime(start,'%Y-%m-%d')
        e=datetime.strptime(end,'%Y-%m-%d')
        if st>e:
            if e>datetime.today():
                print("Please enter an end date earlier than tomorrow")
            else:
                print("Please enter a start date that is earlier than your end date")
        else:
            if self.auth_code:
                end_time='T23:59:59.999Z'
                start_time='T00:00:00.000Z'
                intervals=rrule.rrule(freq=WEEKLY,interval=1,until=e, dtstart=st)
                date_range=[[d.strftime('%Y-%m-%d') + start_time,
                            (d+relativedelta.relativedelta(weeks=1)).strftime('%Y-%m-%d') + end_time] for d in intervals if d<=e]
                time_data=pd.DataFrame()
                for dates in date_range:
                    cycle_url='https://api-7.whoop.com/users/{}/cycles?end={}&start={}'.format(self.whoop_id,
                                                                                           dates[1],
                                                                                           dates[0])
                    data=self.pull_api(cycle_url,df=True)
                    time_data=pd.concat([time_data,data])
                time_data.reset_index(drop=True,inplace=True)

                ## fixing the day column so it's not a list
                time_data['days']=time_data['days'].map(lambda d: d[0])
                time_data.rename(columns={"days":'day'},inplace=True)

                ## Putting all time into minutes instead of milliseconds
                sleep_cols=['qualityDuration','needBreakdown.baseline','needBreakdown.debt','needBreakdown.naps',
                'needBreakdown.strain','needBreakdown.total']
                for sleep_col in sleep_cols:
                    time_data['sleep.' + sleep_col]=time_data['sleep.' + sleep_col].astype(float).apply(lambda x: np.nan if np.isnan(x) else x/60000)

                ## Making nap variable
                time_data['nap_duration']=time_data['sleep.naps'].apply(lambda x: x[0]['qualityDuration']/60000 if len(x)==1 else(
                                                    sum([y['qualityDuration'] for y in x if y['qualityDuration'] is not None])/60000 if len(x)>1 else 0))
                time_data.drop(['sleep.naps'],axis=1,inplace=True)

                ## removing duplicates
                time_data.drop_duplicates(subset=['day','sleep.id'],inplace=True)


                return time_data
            else:
                print("Please run the authorization function first")

    def get_activities_timeframe(self,start,end=datetime.strftime(datetime.utcnow(),"%Y-%m-%d")):
        '''
        Activity data is pulled through the get_keydata functions so if the data pull is present, this function
        just transforms the activity column into a dataframe of activities, where each activity is a row.
        If it has not been pulled, this function runs the key data function then returns the activity dataframe

        If no end date is specified, it will default to today's date.
        '''

        st=datetime.strptime(start,'%Y-%m-%d')
        e=datetime.strptime(end,'%Y-%m-%d')
        if st>e:
            if e>datetime.today():
                print("Please enter an end date earlier than tomorrow")
            else:
                print("Please enter a start date that is earlier than your end date")
        else:

            if self.auth_code:

                if self.sport_dict:
                    sport_dict=self.sport_dict
                else:
                    sports=self.pull_api('https://api-7.whoop.com/sports')
                    sport_dict={sport['id']:sport['name'] for sport in sports}
                    self.sport_dict=self.sport_dict

                ## process activity data
                if self.all_data is not None:
                    ## use existing
                    data=self.all_data
                    data=data[(data.day>=start)&(data.day<=end)].copy(deep=True)
                else:
                    ## pull timeframe data
                    data=self.get_keydata_timeframe(start,end)
                ## now process activities data
                act_data=pd.json_normalize(data[data['strain.workouts'].apply(len)>0]['strain.workouts'].apply(lambda x: x[0]))
                act_data[['during.upper','during.lower']]=act_data[['during.upper','during.lower']].apply(pd.to_datetime)
                act_data['total_minutes']=act_data.apply(lambda x: (x['during.upper']-x['during.lower']).total_seconds()/60.0,axis=1)
                for z in range(0,6):
                     act_data['zone{}_minutes'.format(z+1)]=act_data['zones'].apply(lambda x: x[z]/60000.)
                act_data['sport_name']=act_data.sportId.apply(lambda x: sport_dict[x])

                act_data['day']=act_data['during.lower'].dt.strftime('%Y-%m-%d')
                act_data.drop(['zones','during.bounds'],axis=1,inplace=True)
                act_data.drop_duplicates(inplace=True)
                self.all_activities=act_data
                return act_data
            else:
                print("Please run the authorization function first")


    def get_sleep_timeframe(self,start,end=datetime.strftime(datetime.utcnow(),"%Y-%m-%d")):
        '''
        This function returns sleep metrics in a data frame, for timeframe specified by the user.
        Each row in the data frame represents one night of sleep.

        If no end date is specified, it will default to today's date.

        All sleep times are returned in minutes.
        '''

        st=datetime.strptime(start,'%Y-%m-%d')
        e=datetime.strptime(end,'%Y-%m-%d')
        if st>e:
            if e>datetime.today():
                print("Please enter an end date earlier than tomorrow")
            else:
                print("Please enter a start date that is earlier than your end date")
        else:
            if self.auth_code:
                if self.all_data is not None:
                    ## use existing
                    data=self.all_data
                    data=data[(data.day>=start)&(data.day<=end)].copy(deep=True)
                else:
                    ## pull timeframe data
                    data=self.get_keydata_timeframe(start,end)

                ## getting all the sleep ids
                sleep_ids=data['sleep.id'].values.tolist()
                sleep_list=[int(x) for x in sleep_ids if pd.isna(x)==False]
                if self.all_sleep is not None:
                    ## All sleep data already pulled so just filter
                    all_sleep=self.all_sleep
                    time_sleep=all_sleep[all_sleep.activityId.isin(sleep_list)]
                    return time_sleep

                else:
                    time_sleep=pd.DataFrame()
                    for s in sleep_list:
                        m=self.pull_sleep_main(s)
                        time_sleep=pd.concat([time_sleep,m])

                    ## Cleaning sleep data
                    sleep_update=['qualityDuration','latency','debtPre','debtPost','needFromStrain','sleepNeed',
                                  'habitualSleepNeed','timeInBed','lightSleepDuration','slowWaveSleepDuration',
                                  'remSleepDuration','wakeDuration','arousalTime','noDataDuration','creditFromNaps',
                                  'projectedSleep']

                    for col in sleep_update:
                        time_sleep[col]=time_sleep[col].astype(float).apply(lambda x: np.nan if np.isnan(x) else x/60000)

                    time_sleep.drop(['during.bounds','events'],axis=1,inplace=True)

                    return time_sleep
            else:
                print("Please run the authorization function first")

    def get_sleep_events_timeframe(self,start,end=datetime.strftime(datetime.utcnow(),"%Y-%m-%d")):
        '''
        This function returns sleep events in a data frame, for the time frame specified by the user.
        Each row in the data frame represents an individual sleep event within an individual night of sleep.
        Sleep events can be joined against the sleep or main datasets by sleep id.

        If no end date is specified, it will default to today's date.
        '''

        st=datetime.strptime(start,'%Y-%m-%d')
        e=datetime.strptime(end,'%Y-%m-%d')
        if st>e:
            if e>datetime.today():
                print("Please enter an end date earlier than tomorrow")
            else:
                print("Please enter a start date that is earlier than your end date")
        else:

            if self.auth_code:
                if self.all_data is not None:
                    ## use existing
                    data=self.all_data
                    data=data[(data.day>=start)&(data.day<=end)].copy(deep=True)
                else:
                    ## pull timeframe data
                    data=self.get_keydata_timeframe(start,end)

                ## getting all the sleep ids
                sleep_ids=data['sleep.id'].values.tolist()
                sleep_list=[int(x) for x in sleep_ids if pd.isna(x)==False]
                if self.all_sleep_events is not None:
                    ## All sleep data already pulled so just filter
                    all_sleep_events=self.all_sleep_events
                    time_sleep_events=all_sleep_events[all_sleep_events.id.isin(sleep_list)]
                    return time_sleep_events

                else:
                    if self.all_sleep is not None:
                        sleep_events=self.all_sleep[['activityId','events']]
                        time_sleep=sleep_events[sleep_events.id.isin(sleep_list)]
                        time_sleep_events=pd.concat([pd.concat([pd.json_normalize(events),
                                                                pd.DataFrame({'id':len(events)*[sleep]})],axis=1) for events, sleep in zip(time_sleep['events'],time_sleep['activityId'])])
                    else:
                        time_sleep_events=pd.DataFrame()
                        for s in sleep_list:
                            events=self.pull_sleep_events(s)
                            time_sleep_events=pd.concat([time_sleep_events,events])

                    ## Cleaning sleep events data
                    time_sleep_events['during.lower']=pd.to_datetime(time_sleep_events['during.lower'])
                    time_sleep_events['during.upper']=pd.to_datetime(time_sleep_events['during.upper'])
                    time_sleep_events.drop(['during.bounds'],axis=1,inplace=True)
                    time_sleep_events['total_minutes']=time_sleep_events.apply(lambda x: (x['during.upper']-x['during.lower']).total_seconds()/60.0,axis=1)

                    return time_sleep_events
            else:
                print("Please run the authorization function first")

    def get_hr_timeframe(self,start,end=datetime.strftime(datetime.utcnow(),"%Y-%m-%d"),df=False):
        '''
        This function will pull every heart rate measurement recorded, for the time frame specified by the user.
        The default return for this function is a list of lists, where each "row" contains the date, time, and hr value.
        The measurements are spaced out every ~6 seconds on average.

        To return a dataframe, set df=True. This will take a bit longer, but will return a data frame.

        If no end date is specified, it will default to today's date.

        NOTE: This api pull takes about 6 seconds per week of data ... or 1 minutes for 10 weeks of data,
        so be careful when you pull, it may take a while.
        '''

        st=datetime.strptime(start,'%Y-%m-%d')
        e=datetime.strptime(end,'%Y-%m-%d')
        if st>e:
            if e>datetime.today():
                print("Please enter an end date earlier than tomorrow")
            else:
                print("Please enter a start date that is earlier than your end date")
        else:

            if self.start_datetime:
                athlete_id=self.whoop_id
                start_date=parser.isoparse(self.start_datetime).replace(tzinfo=None)
                end_time='T23:59:59.999Z'
                start_time='T00:00:00.000Z'
                ## using the st and e since it needs the datetime formatted date
                intervals=rrule.rrule(freq=WEEKLY,interval=1,until=e, dtstart=st)
                date_range=[[d.strftime('%Y-%m-%d') + start_time,
                            (d+relativedelta.relativedelta(weeks=1)).strftime('%Y-%m-%d') + end_time] for d in intervals]

                hr_list=[]
                for dates in date_range:
                    start=dates[0]
                    end=dates[1]
                    ul='''https://api-7.whoop.com/users/24590/metrics/heart_rate?end={}&order=t&start={}&step=6'''.format(end,start)
                    hr_vals=self.pull_api(ul)['values']
                    hr_values=[[datetime.utcfromtimestamp(h['time']/1e3).date(),
                                      datetime.utcfromtimestamp(h['time']/1e3).time(),
                                      h['data']] for h in hr_vals]
                    hr_list.extend(hr_values)
                if df:
                    hr_df=pd.DataFrame(hr_list)
                    hr_df.columns=['date','time','hr']
                    return hr_df
                else:
                    return hr_list
            else:
                print("Please run the authorization function first")
