#!/usr/bin/env python
# coding: utf-8

# # Manifold Market Stats

# In[1]:


get_ipython().run_cell_magic('capture', '', '# Install dependencies\n%pip install tabulate\n%pip install plotly\n')


# In[2]:


# Initialize
import os
import time # fix this
import json
import numpy
import requests
import tabulate
import statistics
from random import randrange
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# In[3]:


# CSS formatting for nbconvert output
from IPython.display import display, HTML
HTML("""
<style>
.jp-OutputArea-output.jp-RenderedHTMLCommon table {
  margin-left: auto;
  margin-right: auto;
}
</style>
""")


# In[4]:


scriptTime={}
scriptTime.update({'notebookStarted': datetime.now()})


# Hello! I've had a bunch of questions about how [manifold.markets](https://manifold.markets/) works, and thanks to their public API I can make my own pretty graphs to answer those questions!
# 
# Manifold is a website where anyone can make prediction markets on any topic, which makes it pretty different than most other prediction market sites. But how different is it really? Is it better? Worse? How do we measure "better" or "worse"? Well math, of course! To visualize that math, we can use a bunch of graphs like the ones below. We can watch trends change over time, see how certain variables correlate, and take measurements before/after changes to monitor how they affect the community!
# 
# If you're here from the Manifold Analytics page, you probably know all of that already but welcome anyways. Pretty much all of these plots support zooming and panning around to help you get a better sense of the data.
# 
# Without further ado, let's get started!

# In[5]:


apiTarget = 'https://manifold.wasabipesto.com/api/v0/' # pls no crash server
dataDir   = '../Data/Manifold/prod/' # folder for storing individual market files
cacheTime = timedelta(hours=4)

scriptTime.update({'apiStarted': datetime.now()})
marketsLite = requests.get(apiTarget + 'markets').json()
usersLite = requests.get(apiTarget + 'users').json()

while True:
    lastID = marketsLite[len(marketsLite)-1]['id']
    response = requests.get(apiTarget + 'markets?before=' + lastID).json()
    if len(response) > 0:
        [marketsLite.append(i) for i in response]
    else:
        break

toUpdate = []
for market in marketsLite:
    try:
        if datetime.fromtimestamp(os.path.getmtime(dataDir + market['id'] + '.json')) < datetime.now() - cacheTime:
            toUpdate.append(market['id'])
    except FileNotFoundError:
        toUpdate.append(market['id'])

for mktID in toUpdate:
    reqResponse = requests.get(apiTarget + 'market/' + mktID).json()
    with open(dataDir + mktID + '.json', 'w') as file:
        json.dump(reqResponse, file)
        
scriptTime.update({'apiEnded': datetime.now()})


# In[6]:


# DEFINE SETTINGS
# Global options that are dictated by my opinion.
# Really only put things here if used in mutiple cells, most things will be per-cell.

hBuckets = 100

colorsYN = { # more default colors?
    'YES': 'rgba(99,110,250,1)', 
    'NO': 'rgba(239,85,59,1)'
}

lookbackBinsStd = {
    '1 day':   1,
    '1 week':  7,
    '1 month': 30,
    '1 year':  365,
}

probBuckets=[0.01,0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95,0.99]


# In[7]:


# COLLATE MARKET DATA
# Goal: Have a dict/list of all valid markets with all valid data. 
#       Leave an item out if there is no valid data (close date) and have
#       a try/except in each cell to ignore markets without relevant data.

marketsFull = []
for path, subdirs, files in os.walk(dataDir):
    for name in files:
        with open(os.path.join(path, name)) as jsonData:
            newMarket = json.load(jsonData)
            marketsFull.append(newMarket)

marketSummary = {} 
for market in marketsFull:

    try:
        marketSummary[market['id']]={
            'id': market['id'],
            'url': market['url'],
            'creatorUsername': market['creatorUsername'],
            'numBets': len(market['bets']),
            'totalValue': 0,
            'numComments': len(market['comments']),
            'question': market['question'],
            'outcomeType': market['outcomeType'],
            'mechanism': market['mechanism'],
            'createdTime': datetime.utcfromtimestamp(int(market['createdTime'])/1000),
            'closeTime': datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800)),
            'openLength': datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800)) - datetime.utcfromtimestamp(int(market['createdTime']/1000)),
            'isResolved': market['isResolved'],
        }
    except KeyError:
        print('Error on Market ID #' + market['id'])
    
    try:
        marketSummary[market['id']].update({'volume': market['volume']})
    except KeyError:
        pass
    
    
    if market['mechanism'] == 'cpmm-1':
        # CPMM markets start with $100 ante but it isn't a bet
        marketSummary[market['id']]['totalValue']+=100
    for bet in market['bets']:
        valueToAdd=bet['amount']
        # selling shares subtracts value
        if bet['shares'] < 0:
            valueToAdd=-1*valueToAdd
        # sum all bets
        marketSummary[market['id']]['totalValue']+=valueToAdd
    
    isSerious=True
    for tag in market['tags']:
        if tag == 'personal' or tag == 'fun':
            # no fun allowed
            isSerious=False
    marketSummary[market['id']].update({'isSerious': isSerious})
    
    if marketSummary[market['id']]['createdTime'] > datetime(2022,4,28) and marketSummary[market['id']]['createdTime'] < datetime(2022,6,23):
        dailyFreeMarket=True
    else:
        dailyFreeMarket=False
    for testmarket in marketsLite:
        if (
            testmarket['creatorUsername'] == market['creatorUsername'] and 
            marketSummary[market['id']]['createdTime'].date() == datetime.utcfromtimestamp(int(testmarket['createdTime'])/1000).date() and
            marketSummary[market['id']]['createdTime'] > datetime.utcfromtimestamp(int(testmarket['createdTime'])/1000)
        ):
            dailyFreeMarket=False
    marketSummary[market['id']].update({'dailyFreeMarket': dailyFreeMarket})
    
    isOpen=True
    try:
        if datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800)) < datetime.now():
            isOpen=False
    except KeyError:
        pass
    marketSummary[market['id']].update({'isOpen': isOpen})
    
    try: # free response markets don't have probability
        if not market['probability'] == None:
            marketSummary[market['id']].update({
                'instProb': market['probability'],
            })
    except KeyError:
        pass
    
    try: # getting fixed?
        if market['createdTime'] < market['closeTime']:
            marketSummary[market['id']].update({
                'closeTime': datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800)),
                'openLength': datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800)) - datetime.utcfromtimestamp(int(market['createdTime']/1000)),
                # add isOpen ?
            })
    except KeyError:
        pass

    try: # obviously for resolved markets
        marketSummary[market['id']].update({
            'resolutionTime': datetime.utcfromtimestamp(int(market['resolutionTime'])/1000),
            'resolution': market['resolution'],
        })
        
        resolutionLength = datetime.utcfromtimestamp(int(market['resolutionTime']/1000)) - datetime.utcfromtimestamp(min(int(market['closeTime'])/1000,253401772800))
        if resolutionLength.seconds > 0 and resolutionLength.days < 3500:
            marketSummary[market['id']].update({
                'resolutionLength': resolutionLength,
            })
    except KeyError:
        pass
    
    try:
        marketSummary[market['id']].update({'resolutionProbability': market['resolutionProbability']})
    except KeyError:
        pass
    
    # THIS AREA IS ONLY FOR COOL KIDS WITH MULTIPLE BETS
    if len(market['bets']) <= 1:
        # megamind face: no bets?
        continue
    try:
        betSum=0
        betNum=1
        for bet in market['bets']:
            if betNum == 1:
                # first bet: look back
                betLen=bet['createdTime']-market['createdTime']
                betSum+=bet['probBefore']*betLen
                prevTime=bet['createdTime']
            elif betNum == len(market['bets']):
                # last bet: look back
                betLen=bet['createdTime']-prevTime
                betSum+=bet['probBefore']*betLen
                # last bet: look forward
                betLen=market['closeTime']-bet['createdTime']
                betSum+=bet['probAfter']*betLen
            else:
                # regular bet: look back
                betLen=bet['createdTime']-prevTime
                betSum+=bet['probBefore']*betLen
                prevTime=bet['createdTime']
            betNum+=1
        mktLen=market['closeTime']-market['createdTime']
        avgProb=betSum/mktLen
        
        marketSummary[market['id']].update({
            'avgProb': avgProb,
            'betAmountTotal': sum(bet['amount'] for bet in market['bets']),
            'betAmountAverage': statistics.mean(bet['amount'] for bet in market['bets']),
        })
    except KeyError:
        pass
    except TypeError:
        #print(market['id'])
        pass # I don't think we need this catch for prod data
    
    try: # brier uses avgProb not instProb
        if market['resolution'] == 'YES':
            brierScore=(marketSummary[market['id']]['avgProb']-1)**2
            marketSummary[market['id']].update({'brierScore': brierScore})
        elif market['resolution'] == 'NO':
            brierScore=(marketSummary[market['id']]['avgProb']-0)**2
            marketSummary[market['id']].update({'brierScore': brierScore})

    except KeyError:
        pass


# In[8]:


creatorSummary = {}
for market in marketSummary.values():
    user=market['creatorUsername']

    if not user in creatorSummary:
        creatorSummary[user]={
            'creatorUsername': user,
            'marketsCreated': 0,
            'volumeTotal': 0,
            'volumeAverage': 0,
            'volumeTotalSerious': 0,
            'valueTotal': 0,
            'valueAverage': 0,
            'valueTotalSerious': 0,
            'numBetsTotal': 0,
            'numBetsAverage': 0,
            'numCommentsTotal': 0,
            'numCommentsAverage': 0,
            'betAmountTotal': 0,
            'betAmountAverage': 0,
            'brierScoreSum': 0,
            'brierScoreCount': 0,
            'brierScoreAvg': 1,
        }

    creatorSummary[user]['marketsCreated'] += 1
    
    try:
        creatorSummary[user]['volumeTotal']  += market['volume']
        creatorSummary[user]['volumeAverage'] = creatorSummary[user]['volumeTotal'] / creatorSummary[user]['marketsCreated']
        if market['isSerious']:
            creatorSummary[user]['volumeTotalSerious'] += market['volume']
    except KeyError:
        pass
        
    try:
        creatorSummary[user]['valueTotal']  += market['totalValue']
        creatorSummary[user]['valueAverage'] = creatorSummary[user]['totalValue'] / creatorSummary[user]['marketsCreated']
        if market['isSerious']:
            creatorSummary[user]['valueTotalSerious'] += market['totalValue']
    except KeyError:
        pass
        
    creatorSummary[user]['numBetsTotal']  += market['numBets']
    creatorSummary[user]['numBetsAverage'] = creatorSummary[user]['numBetsTotal'] / creatorSummary[user]['marketsCreated']
    creatorSummary[user]['numCommentsTotal']  += market['numComments']
    creatorSummary[user]['numCommentsAverage'] = creatorSummary[user]['numCommentsTotal'] / creatorSummary[user]['marketsCreated']
    
    try:
        creatorSummary[user]['betAmountTotal']  += market['betAmountTotal']
        creatorSummary[user]['betAmountAverage'] = creatorSummary[user]['betAmountTotal'] / creatorSummary[user]['marketsCreated']
    except KeyError:
        pass

    try:
        creatorSummary[user]['brierScoreSum'] += market['brierScore'] or 0
        if not market['brierScore'] == 0:
            creatorSummary[user]['brierScoreCount'] += 1
        if creatorSummary[user]['brierScoreCount'] >= 2: # only start calculating average brier score if there's at least 2 relevant markets
            creatorSummary[user]['brierScoreAvg'] = (creatorSummary[user]['brierScoreSum']) / creatorSummary[user]['brierScoreCount']
    except KeyError:
        pass


# In[9]:


betSummary = {}
for market in marketsFull:
    for bet in market['bets']:

        if not bet['id'] in betSummary:
            betSummary[bet['id']]={
                'betID': bet['id'],
                'marketID': market['id'],
                'bettorID': bet['userId'],
                'createdTime': datetime.utcfromtimestamp(int(bet['createdTime'])/1000),
                'outcome': bet['outcome'],
                'amount': bet['amount'],
                'shares': bet['shares'],
                'probBefore': bet['probBefore'],
                'probAfter': bet['probAfter'],
                'isResolved': market['isResolved'],
            }
        
        try:
            betSummary[bet['id']]['loanAmount'] = bet['loanAmount']
        except KeyError:
            pass

        try:
            betSummary[bet['id']]['platformFee'] = bet['fees']['platformFee']
        except KeyError:
            pass
        


# In[10]:


userSummary = {}
for user in usersLite:
    try:
        userSummary[user['id']]={
            'id': user['id'],
            'displayname': user['name'],
            'username': user['username'],
            'createdTime': datetime.utcfromtimestamp(int(user['createdTime'])/1000),
            'balance': user['balance'],
            'totalDeposits': user['totalDeposits'],
            'totalProfit': user['profitCached']['allTime'],
        }
    except KeyError:
        print('Error on User ID #' + user['id'])
        
# o7
deadUsers = ['k6m4sXdz90OxEEKrUaSSwYH7aal2']
for userid in deadUsers:
    userSummary[userid]={
        'id': userid,
        'displayname': 'Deactivated',
        'username': 'Deactivated',
        'createdTime': datetime(2022,1,1),
        'balance': 0,
        'totalDeposits': 0,
        'totalProfit': 0,
    }


# In[11]:


bettorSummary = {}
for bet in betSummary.values():

    if not bet['bettorID'] in bettorSummary:
        bettorSummary[bet['bettorID']]={
            'bettorId': bet['bettorID'],
            'bettorUsername': 'Anonymous',
            'betAmounts': [],
            'betDates': [],
            'payoutAmounts': [],
            #'brierScores': [],
        }

    bettorSummary[bet['bettorID']]['betAmounts'].append(bet['amount'])
    bettorSummary[bet['bettorID']]['betDates'].append(bet['createdTime'])

    try:
        bettorSummary[bet['bettorID']]['payoutAmounts'].append(bet['payout'])
    except KeyError:
        pass

for bettor in bettorSummary.values():
    bettorSummary[bettor['bettorId']].update({
        'numBets': len(bettor['betAmounts']),
        'firstBet': min(bettor['betDates']),
        'betAmountTotal': sum(bettor['betAmounts']),
        #'betAmountAverage': statistics.mean(abs(amt) for amt in bettor['betAmounts']),
        'payoutAmountTotal': sum(bettor['payoutAmounts']),
        #'betAmountAverage': statistics.mean(bettor['payoutAmounts']),
        #'brierScoreAvg': statistics.mean(bettor['brierScores']),
    })

for market in marketsFull:
    try:
        for answer in market['answers']:
            bettorSummary[answer['userId']]['bettorUsername']=answer['username']
    except KeyError:
        pass

for user in userSummary.values():
    try:
        bettorSummary[user['id']]['bettorUsername']=user['username']
    except KeyError:
        pass # not every user bets


# In[12]:


# WIP WIP WIP WIP WIP WIP WIP WIP WIP
transactionTypes = {
    # System Deposits
    'startingBalance': {
        'label': 'Starting Balance',
        'description': 'The balance provided to you by Manifold when you register your account.',
    },
    'manaPurchase': {
        'label': 'Mana Purchased',
        'description': 'Amount of M$ earned from real-money purchases.',
    },
    # Market Investments
    'betBought': {
        'label': 'Purchased Bets',
        'description': 'Amount spent purchasing shares in a market, investing in a position.',
    },
    'betSold': {
        'label': 'Sold Bets',
        'description': 'Amount earned selling shares in a market, cashing out of your position.',
    },
    'liquidityBought': {
        'label': 'Liquidity Purchased',
        'description': 'Amount spent injecting liquidity into a market',
    },
    'liquiditySold': {
        'label': 'Liquidity Withdrawn',
        'description': 'Amount earned retrieving liquidity from a market',
    },
    'marketResolved': {
        'label': 'Market Resolved',
        'description': 'Amount earned from owned shares upon market resolution.',
    },
    'marketCancelled': {
        'label': 'Market Cancelled',
        'description': 'Amount reverted from market cancellation.',
    },
    # User Interactions
    'tipOut': {
        'label': 'Tips Sent',
        'description': 'Amount sent to others via tipping.',
    },
    'tipIn': {
        'label': 'Tips Received',
        'description': 'Amount recieved from tips.',
    },
    'manalinkOut': {
        'label': 'Manalinks Sent',
        'description': 'Amount sent to others via manalinks.',
    },
    'manalinkIn': {
        'label': 'Manalinks Received',
        'description': 'Amount recieved from manalinks.',
    },
    # System Withdrawls
    'charity': {
        'label': 'Charity',
        'description': 'Amount donated to charity.',
    },
}

transactionTypesNet = {
    'realizedProfit': {
        'label': 'Net Market Profit',
        'description': 'Net amount recieved from market investment.',
    },
    'unrealizedProfit': {
        'label': 'Unrealized Market Profit',
        'description': 'Unrealized amount from market investment.',
    },
    'interactions': {
        'label': 'User Interaction',
        'description': 'Net profit from user interactions',
    },
}


# In[13]:


# WIPWIPWIPWIPWIPWIPWIPWIP OH MY GOD WIP
transactionLog = {}

## System Deposits
for user in userSummary.values():
    transactionLog[user['id']] = []
    transactionLog[user['id']].append({
        'type': 'startingBalance',
        'time': user['createdTime'],
        'amount': 1000
    })

    transactionLog[user['id']].append({
        'type': 'manaPurchase',
        'time': user['createdTime'],
        'amount': user['totalDeposits']
    })

## Market Investments
for bet in betSummary.values():
    if bet['amount'] > 0:
        transactionLog[bet['bettorID']].append({
            'type': 'betBought',
            'time': bet['createdTime'],
            'amount': bet['amount'] * -1
        })
    if bet['amount'] < 0:
        transactionLog[bet['bettorID']].append({
            'type': 'betSold',
            'time': bet['createdTime'],
            'amount': bet['amount'] * -1
        })

# TODO: Liquidity purchased, liquidity sold

for market in marketSummary.values():
    if not market['isResolved']:
        continue
    if market['mechanism'] == 'cpmm-1':
        
        # market cancelled, refund all shares
        if market['resolution'] == 'CANCEL':
            for marketSelect in marketsFull:
                if marketSelect['id'] == market['id']:
                    for bet in marketSelect['bets']:
                        transactionLog[bet['bettorID']].append({
                            'type': 'marketCancelled',
                            'time': market['createdTime'],
                            'amount': bet['amount']
                        })
                break
        continue
        
        # calculate net shares per user
        netShares = {}
        for marketSelect in marketsFull:
            if marketSelect['id'] == market['id']:
                for bet in marketSelect['bets']:
                    if not bet['userId'] in netShares:
                        netShares[bet['userId']] = 0
                    if bet['outcome'] == 'YES':
                        netShares[bet['userId']]+=bet['shares']
                    elif bet['outcome'] == 'NO':
                        netShares[bet['userId']]-=bet['shares']
            break
        
        # calculate & distribute payout
        if market['resolution'] == 'YES':
            resolutionPCT=1
        elif market['resolution'] == 'NO':
            resolutionPCT=0
        elif market['resolution'] == 'MKT':
            try:
                resolutionPCT=market['resolutionProbability']
            except KeyError: # why???
                resolutionPCT=None
        
        for user in userShares.keys():
            payout = (netShares[user]*resolutionPCT) + (1-netShares[user])*(1-resolutionPCT)
            transactionLog[user].append({
                'type': 'marketResolved',
                'time': market['closeTime'],
                'amount': payout,
            })

## User Interactions
# TODO: Tips
# TODO: Manalinks

## System Withdrawls
# TODO: Charity

for user in userSummary.values():
    userSummary[user['id']]['calculatedBalance'] = sum([txn['amount'] for txn in transactionLog[user['id']]])
    
#print(userSummary['L5GMbV3aY2e2L5t5BIpjKDbZfJv1'])


# ## Market Creation, Closure, Resolution, and Length

# In[14]:


chartLabels = {
    'createdTime': 'Created',
    'closeTime': 'Closed',
    'resolutionTime': 'Resolved',
}

chartData = {}
for prop in chartLabels:
    chartData[prop]=[]
    for market in marketSummary.values():
        try:
            chartData[prop].append(market[prop])
        except:
            pass

fig = go.Figure()
for prop in chartLabels:
    fig.add_trace(go.Histogram(
        x=chartData[prop],
        name=chartLabels[prop]
    ))
fig.update_traces(
    xbins_size=timedelta(days=5) / timedelta(milliseconds=1),
    xbins_start=min(chartData['createdTime']),
    xbins_end=max(chartData['createdTime']) + timedelta(days=10000) # consider lifting?
)
fig.update_layout(
    title_text='Histogram: Market Open, Close, and Resolution Dates',
    xaxis_title_text='Date',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[
    min(chartData['createdTime']),
    max(chartData['createdTime']) + timedelta(days=180)
])
fig.update_yaxes(range=[
    0,400 # make this adapt
])
fig.add_annotation(
    x=datetime(2022,4,27), y=0,
    ax=0, ay=-150,
    text='Free Markets<br />Introduced',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=datetime(2022,6,24), y=0,
    ax=0, ay=-150,
    text='Free Markets<br />on Hiatus',
    bgcolor='white', opacity=0.95
)
fig.show()


# > This chart is a pretty good breakdown of Manifold's history and potential future. The first few months are spotty, with big groups of markets being created as users join the site but not a lot of market conclusions or resolutions. My guess is a lot of markets were created as mirrors from other sites, like Metaculus, which are generally longer-term. As users joined in February, lots of smaller and shorter markets were created. A large number of markets are opened, often more than double the number of markets closed. This difference implies an ever-growing pool of open questions. (Market resolutions generally track pretty closely to market closings. We'll look more at that later.) And finally, stretching out to the right we can see the stretch of scheduled market closures in the future. Zoom out to see just how far the rabbit hole goes...

# In[15]:


chartLabels = {
    'openLength': 'Open Length',
}

chartData = {}
for prop in chartLabels:
    chartData[prop]=[]
    for market in marketSummary.values():
        try:
            chartData[prop].append(market[prop].days)
        except:
            pass

fig = go.Figure()
for prop in chartLabels:
    fig.add_trace(go.Histogram(
        x=chartData[prop],
        name=chartLabels[prop],
        marker_color='rgba(0,140,100,1)',
    ))
fig.update_traces(
    xbins_size=3,
    xbins_start=0,
    xbins_end=10000
)
fig.update_layout(
    title_text='Histogram: Market Open Length',
    xaxis_title_text='Days',
    yaxis_title_text='Count', 
    bargap=0.1
)
fig.update_xaxes(range=[0,400])
fig.add_annotation(
    x=statistics.median(chartData['openLength']), y=0,
    ax=0, ay=-100,
    text='Median',
    xanchor='left'
)
fig.add_annotation(
    x=numpy.percentile(chartData['openLength'],75), y=0,
    ax=0, ay=-50,
    text='75th Percentile',
    xanchor='left',
)
fig.show()


# In[16]:


lookbackBins = lookbackBinsStd
tableSubject='Market Length'
tableHeaders=['Markets created in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['Number of Markets'],
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemList = []
    for market in marketSummary.values():
        try: 
            if market['createdTime'] > datetime.now() - timedelta(days=lookbackTime):
                itemList.append(market['openLength'].days)
        except KeyError:
            pass
    tableData[0].append(len(itemList))
    tableData[1].append(round(numpy.percentile(itemList,5),0))
    tableData[2].append(round(statistics.mean(itemList),0))
    tableData[3].append(round(statistics.median(itemList),0))
    tableData[4].append(round(numpy.percentile(itemList,95),0))

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('days')
tableData[0][len(tableData)]='markets'

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > This chart surprised me when I first saw it, due to the sheer number of very short markets. An ongoing problem facing many prediction sites is how to encourage betting on (and creating) very long-term markets. Aside from a few outliers, the vast majority of all markets are less than one year. Most are less than a few months, and a very large proportion are even less than one day. There are some explanations for the extremely short markets, such as users testing market functions, betting on intraday market outcomes, or "farming" daily free market proceeds. 

# In[17]:


chartLabels = {
    'resolutionLength': 'Time to Resolve',
}

chartData = {}
for prop in chartLabels:
    chartData[prop]=[]
    for market in marketSummary.values():
        try:
            chartData[prop].append(market[prop].days)
        except:
            pass

fig = go.Figure()
for prop in chartLabels:
    fig.add_trace(go.Histogram(
        x=chartData[prop],
        name=chartLabels[prop],
        marker_color='rgba(100,0,140,1)',
    ))
fig.update_traces(
    xbins_size=1,
    xbins_start=0,
    xbins_end=1000
)
fig.update_layout(
    title_text='Histogram: Time to Resolve',
    xaxis_title_text='Days',
    yaxis_title_text='Count', 
    bargap=0.1
)
fig.update_xaxes(range=[
    0, max(chartData['resolutionLength'])
])
fig.add_annotation(
    x=numpy.percentile(chartData['resolutionLength'],95), y=0,
    ax=0, ay=-50,
    text='95th Percentile',
    xanchor='left',
)
fig.show()


# In[18]:


lookbackBins = lookbackBinsStd
tableSubject='Time to Resolve'
tableHeaders=['Markets resolved in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemList = []
    for market in marketSummary.values():
        try: 
            if market['createdTime'] > datetime.today() - timedelta(days=lookbackTime):
                itemList.append(market['resolutionLength'].seconds/3600) # not doing what I think it does, hide until fixed
        except KeyError:
            pass
    try:
        tableData[0].append(round(numpy.percentile(itemList,5),1))
        tableData[1].append(round(statistics.mean(itemList),1))
        tableData[2].append(round(statistics.median(itemList),1))
        tableData[3].append(round(numpy.percentile(itemList,95),1))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('hours')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
#table


# > Aside from a few very [famous](https://manifold.markets/DrP/will-donald-trump-by-the-president) exceptions, I was quite pleased with the number of markets resolved quickly.
# In fact, most markets do so in less than a day!

# In[19]:


lookbackBins = lookbackBinsStd
tableSubject='Resolution Rate'
tableHeaders=['Markets closed in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    [tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemDict = {'sum': 0, 'count': 0}
    for market in marketSummary.values():
        try: 
            if market['closeTime'] > datetime.today() - timedelta(days=lookbackTime) and market['closeTime'] < datetime.today():
                if market['isResolved']:
                    itemDict['sum']+=1
                itemDict['count']+=1
        except KeyError:
            pass
    try:
        tableData[0].append(round(itemDict['sum']/itemDict['count']*100,1))
    except ZeroDivisionError:
        tableData[0].append('N/A')

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('%')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > Manifold devs are currently implementing a feature for automatic resolution! There used to be a rant here about how there was a ~10% chance your mana would be locked away forever, but the team is currently [working on](https://github.com/manifoldmarkets/manifold/pull/506) an alternative.

# ## Market Types and Mechanisms

# In[20]:


timestampByMechanisim = {}
for market in marketSummary.values():
    try:
        timestampByMechanisim[market['mechanism'].upper()].append(market['createdTime'])
    except KeyError:
        timestampByMechanisim[market['mechanism'].upper()]=[market['createdTime']]

timestampByOutcome = {}
for market in marketSummary.values():
    try:
        timestampByOutcome[market['outcomeType'].upper()].append(market['createdTime'])
    except KeyError:
        timestampByOutcome[market['outcomeType'].upper()]=[market['createdTime']]
        
timestampByResolution = {'YES': [], 'NO': [], 'CANCEL': [], 'MKT': []} # only get standard resolutions
for market in marketSummary.values():
    try:
        timestampByResolution[market['resolution'].upper()].append(market['createdTime'])
    except KeyError:
        pass


# In[21]:


fig = make_subplots(
    rows=1, cols=3, 
    specs=[[{"type": "pie"}, {"type": "pie"}, {"type": "pie"}]],
    subplot_titles=("Market Mechanism", "Outcome Type", "Resolution (Non-Numeric)")
)
fig.add_trace(go.Pie(
    labels=list(timestampByMechanisim.keys()),
    values=list(len(timestampByMechanisim[i]) for i in timestampByMechanisim)
    ), row=1, col=1
)
fig.add_trace(go.Pie(
    labels=list(timestampByOutcome.keys()),
    values=list(len(timestampByOutcome[i]) for i in timestampByOutcome)
    ), row=1, col=2
)
fig.add_trace(go.Pie(
    labels=list(timestampByResolution.keys()),
    values=list(len(timestampByResolution[i]) for i in timestampByResolution)
    ), row=1, col=3
)
fig.update_traces(
    showlegend=False,
    textinfo='label+text',
    textposition='outside',
    hoverinfo='value+percent'
)
fig.update_layout(
    title_text='Total Count per Property',
    height=400
)
fig.update_annotations(y=1.1)
fig.show()


# In[22]:


fig = make_subplots(
    rows=3, cols=1, 
    specs=[[{"type": "histogram"}], [{"type": "histogram"}], [{"type": "histogram"}]],
    subplot_titles=("Market Mechanism", "Outcome Type", "Resolution (Non-Numeric)")
)
for i in timestampByMechanisim:
    fig.add_trace(go.Histogram(
        x=timestampByMechanisim[i],
        name=i
    ), row=1, col=1 )
for i in timestampByOutcome:
    fig.add_trace(go.Histogram(
        x=timestampByOutcome[i],
        name=i
    ), row=2, col=1 )
for i in timestampByResolution:
    fig.add_trace(go.Histogram(
        x=timestampByResolution[i],
        name=i
    ), row=3, col=1 )
fig.update_traces(
    xbins_size=timedelta(days=1) / timedelta(milliseconds=1),
    showlegend=False
)
fig.update_layout(
    title_text='Histogram: Property vs Creation Date',
    barmode='stack',
    height=1000,
    bargap=0.1
)
fig.update_xaxes(range=[
    min(timestampByOutcome['BINARY']),
    max(timestampByOutcome['BINARY'])
])

fig.add_annotation(
    x=datetime(2022,3,15), y=0, yref='y1',
    ax=0, ay=-150,
    text='CPMM-1<br />Conversion',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=datetime(2022,2,17), y=0, yref='y2',
    ax=0, ay=-150,
    text='Free-Response<br />Introduced',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=datetime(2022,5,19), y=0, yref='y2',
    ax=0, ay=-150,
    text='Numeric<br />Introduced',
    bgcolor='white', opacity=0.95
)

fig['layout']['xaxis']['title']='Date'
fig['layout']['yaxis']['title']='Count'
fig['layout']['xaxis2']['title']='Date'
fig['layout']['yaxis2']['title']='Count'
fig['layout']['xaxis3']['title']='Date'
fig['layout']['yaxis3']['title']='Count'
fig.show()


# > This is another great look at manifold's history. In the first plot you can see the market mechanism slowly changing over time, from mostly DPM markets to mostly CPMM. The second plot shows the trend from entirely-binary markets to a slow incorporation of free response, and now a few numeric markets being thrown in the mix. The last plot is mostly for fun, but it is neat to see the number of canceled  markets as time goes on.

# In[23]:


itemList = []
for market in marketSummary.values():
    try:
        if market['volume'] > 0:
            itemList.append(market['volume'])
    except KeyError:
        pass
    except TypeError:
        pass

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=itemList,
    marker_color='rgba(20,20,20,0.8)'
))
fig.update_traces(
    xbins_size=50,
    xbins_start=0,
    xbins_end=500000
)
fig.update_layout(
    title_text='Histogram: Market Volume',
    xaxis_title_text='M$',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[0,5000])
fig.add_annotation(
    x=statistics.median(itemList), y=0,
    ax=0, ay=-100,
    text='Median',
    xanchor='left',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=numpy.percentile(itemList,75), y=0,
    ax=0, ay=-50,
    text='75th Percentile',
    xanchor='left',
)
fig.show()


# In[24]:


lookbackBins = lookbackBinsStd
tableSubject='Market Volume'
tableHeaders=['Markets created in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemList = []
    for market in marketSummary.values():
        try: 
            if market['createdTime'] > datetime.today() - timedelta(days=lookbackTime):
                itemList.append(market['volume'])
        except KeyError:
            pass
    try:
        tableData[0].append(round(numpy.percentile(itemList,5),2))
        tableData[1].append(round(statistics.mean(itemList),2))
        tableData[2].append(round(statistics.median(itemList),2))
        tableData[3].append(round(numpy.percentile(itemList,95),2))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('M$')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > What's in a bet? Well every trade in a market gets added up to make the volume, so this is a pretty good indicator of how much attention a market is getting. The dropoff is not as steep as I expected, there are markets getting routinely more than $300 in volume. Of course, this will be biased towards markets that have been open longer.
# 
# > The problem with this metric is that if you sell a bet, that increases the volume but not the market's value! Volume counts each transaction as a net positive, no matter the impact. This is useful if you're looking for markets with lots of activity (selling is still activity!) but not great for determining how much money is at stake.

# In[25]:


itemList = []
for market in marketSummary.values():
    try:
        if market['totalValue'] > 0:
            itemList.append(market['totalValue'])
    except KeyError:
        pass
    except TypeError:
        pass

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=itemList,
    marker_color='rgba(20,20,20,0.8)'
))
fig.update_traces(
    xbins_size=50,
    xbins_start=0,
    xbins_end=500000
)
fig.update_layout(
    title_text='Histogram: Total Market Value',
    xaxis_title_text='M$',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[100,5000])
fig.add_annotation(
    x=statistics.median(itemList), y=0,
    ax=0, ay=-100,
    text='Median',
    xanchor='left',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=numpy.percentile(itemList,75), y=0,
    ax=0, ay=-50,
    text='75th Percentile',
    xanchor='left',
)
fig.show()


# In[26]:


lookbackBins = lookbackBinsStd
tableSubject='Total Market Value'
tableHeaders=['Markets created in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemList = []
    for market in marketSummary.values():
        try: 
            if market['createdTime'] > datetime.today() - timedelta(days=lookbackTime):
                itemList.append(market['volume'])
        except KeyError:
            pass
    try:
        tableData[0].append(round(numpy.percentile(itemList,5),2))
        tableData[1].append(round(statistics.mean(itemList),2))
        tableData[2].append(round(statistics.median(itemList),2))
        tableData[3].append(round(numpy.percentile(itemList,95),2))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('M$')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > Market value is a newer metric that more accurately represents how much money's at stake. There's a couple different systems at play but the concept is the same for both: this is the total amount for each market that will be distributed to the winners. For free-response markets this is the total amount of money in the payout pool, which will be distributed evenly to all shares in the winning bucket(s). For binary markets this is one-half of the total number of shares, since the number of YES and NO shares is always equal and only half of them will ever pay out.

# ## Binary Market Resolutions and Probabilities

# In[27]:


timestampByResolutionYN = {'YES': [], 'NO': []} # only capture standard resolutions
for market in marketSummary.values():  # produces a dict with {key, [value, ...]} of {resolution, [length, length...]}
    try:
        timestampByResolutionYN[market['resolution']].append(market['createdTime'])
    except KeyError:
        pass

qLengthByResolutionYN = {'YES': [], 'NO': []}
for market in marketSummary.values():
    try:
        qLengthByResolutionYN[market['resolution']].append(len(market['question']))
    except KeyError:
        pass

volumeByResolutionYN = {'YES': [], 'NO': []}
for market in marketSummary.values():
    try:
        volumeByResolutionYN[market['resolution']].append(market['totalValue'])
    except KeyError:
        pass


# In[28]:


fig = make_subplots(
    rows=3, cols=1, 
    specs=[[{"type": "histogram"}], [{"type": "histogram"}], [{"type": "histogram"}]],
    subplot_titles=("Market Creation Date", "Question Length", "Market Value")
)
for YN in colorsYN:
    fig.add_trace(go.Histogram(
        x=timestampByResolutionYN[YN],
        marker_color=colorsYN[YN],
        name=YN,
        xbins_size=timedelta(days=3) / timedelta(milliseconds=1),
        xbins_start=min(timestampByResolutionYN['YES']),
        xbins_end=max(timestampByResolutionYN['YES']),
    ), row=1, col=1 )
    fig.add_trace(go.Histogram(
        x=qLengthByResolutionYN[YN],
        marker_color=colorsYN[YN],
        name=YN,
        xbins_size=3
    ), row=2, col=1 )
    fig.add_trace(go.Histogram(
        x=volumeByResolutionYN[YN],
        marker_color=colorsYN[YN],
        name=YN,
        xbins_size=50,
        xbins_start=0,
        xbins_end=5000
    ), row=3, col=1 )
fig.update_traces(
    showlegend=False
)
fig.update_layout(
    title_text='Histogram: Binary Resolution vs Property',
    height=1000,
    bargap=0.1
)

fig.add_annotation(
    x=datetime(2022,4,27), y=0,
    ax=0, ay=-150,
    text='Free Markets<br />Introduced',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=datetime(2022,6,24), y=0,
    ax=0, ay=-150,
    text='Free Markets<br />on Hiatus',
    bgcolor='white', opacity=0.95
)

fig['layout']['xaxis']['title']='Date'
fig['layout']['yaxis']['title']='Count'
fig['layout']['xaxis2']['title']='Characters'
fig['layout']['yaxis2']['title']='Count'
fig['layout']['xaxis3']['title']='M$'
fig['layout']['yaxis3']['title']='Count'
fig.show()


# > I wasn't expecting these graphs to be useful at all, but they're actually pretty neat. These plots only show markets that have been resolved to just YES or NO, so it doesn't cover everything. The first plot shows a *lot* of YES markets recently. Maybe due to free market farming? Or maybe shorter markets are more likely to resolve yes? In the same vein there's also a definite grouping of YES in the short end of the question length.

# In[29]:


get_ipython().run_cell_magic('capture', '', "probabilityByResStatus={'Resolved': [], 'Unresolved': []}\nfor market in marketSummary.values():\n    try:\n        if market['isResolved']:\n            probabilityByResStatus['Resolved'].append(market['instProb'])\n        else:\n            probabilityByResStatus['Unresolved'].append(market['instProb'])\n    except KeyError:\n        pass\n\nfig = go.Figure()\nfor resStatus in probabilityByResStatus:\n    fig.add_trace(go.Histogram(\n        x=probabilityByResStatus[resStatus],\n        name=resStatus\n    ))\nfig.update_traces(\n    xbins_size=0.01,\n    xbins_start=0,\n    xbins_end=1,\n)\nfig.update_layout(\n    title_text='Histogram: All Market Probabilities',\n    xaxis_title_text='Probability',\n    yaxis_title_text='Count',    \n    barmode='stack',\n    bargap=0,\n    bargroupgap=0.2\n)\nfig.layout.xaxis.tickformat = ',.0%'\nfig.show()\n")


# In[30]:


get_ipython().run_cell_magic('capture', '', "lookbackBins = lookbackBinsStd\ntableSubject='Probability'\ntableHeaders=['Markets created in the past...']\n[tableHeaders.append(i) for i in lookbackBins.keys()]\n\ntableData=[\n    ['5th Percentile ' + tableSubject],\n    ['Average ' + tableSubject],\n    ['Median ' + tableSubject],\n    ['95th Percentile ' + tableSubject],\n]\n\nfor lookbackTime in lookbackBins.values():\n    itemList = []\n    for market in marketSummary.values():\n        try: \n            if market['createdTime'] > datetime.today() - timedelta(days=lookbackTime):\n                itemList.append(market['instProb']*100)\n        except KeyError:\n            pass\n    try:\n        tableData[0].append(round(numpy.percentile(itemList,5),2))\n        tableData[1].append(round(statistics.mean(itemList),2))\n        tableData[2].append(round(statistics.median(itemList),2))\n        tableData[3].append(round(numpy.percentile(itemList,95),2))\n    except IndexError:\n        tableData[0].append('N/A')\n        tableData[1].append('N/A')\n        tableData[2].append('N/A')\n        tableData[3].append('N/A')\n\ntableHeaders.append('')\nfor i in range(len(tableData)):\n    tableData[i].append('%')\n\ntable = tabulate.tabulate(\n    tableData,\n    headers=tableHeaders,\n    tablefmt='html'\n)\ntable\n")


# In[31]:


resolutionByProb = {}
for bucket in probBuckets:
    resolutionByProb[bucket]={'sum': 0, 'count': 0, 'avg': 0}

for market in marketSummary.values():
    try:
        bucket=min(list(probBuckets), key=lambda x:abs(x-market['instProb'])) # get closest bucket
        if market['resolution'] == 'YES':
            resolutionByProb[bucket]['sum']+=1
            resolutionByProb[bucket]['count']+=1
            resolutionByProb[bucket]['avg']=resolutionByProb[bucket]['sum']/resolutionByProb[bucket]['count']
        elif market['resolution'] == 'NO':
            resolutionByProb[bucket]['count']+=1
            resolutionByProb[bucket]['avg']=resolutionByProb[bucket]['sum']/resolutionByProb[bucket]['count']
    except KeyError:
        pass

refpoint=max(list(resolutionByProb[bucket]['count'] for bucket in probBuckets))

fig = go.Figure()
fig.add_trace(go.Scatter(
    name='All Markets',
    x=list(resolutionByProb.keys()),
    y=list(round(resolutionByProb[bucket]['avg'],3) for bucket in probBuckets),
    mode='markers',
    marker=dict(
        size=list(resolutionByProb[bucket]['count']/refpoint*100 for bucket in probBuckets),
        sizemin=3,
        color=list(resolutionByProb[bucket]['count'] for bucket in probBuckets),
        #colorbar_title='Count',
        colorscale='greens',
        cmin=-0.25*refpoint,
        cmax=0.75*refpoint
    )
))
fig.add_shape(
    type="line",
    x0=0, y0=0, x1=1, y1=1
)
fig.update_layout(
    title_text='Calibration Plot: Binary-Resolved Markets by Probability at Close',
    xaxis_title_text='Probability at Close',
    yaxis_title_text='Resolution',
)
fig.layout.xaxis.tickformat = ',.0%'
fig.layout.yaxis.tickformat = ',.0%'
fig.update_xaxes(range=[0,1])
fig.update_yaxes(range=[0,1])
fig.show()


# > These calibration plots are some of my favorite ways to visualize accuracy. How good is Manifold at actually predicting answers? By the time a market closes we've usually agreed on the right answer or left it somwehere in the middle if we're not sure. On one hand, this is good! It means we aren't wildly off, or at least that we all come to similar conclusions.

# In[32]:


resolutionByProb = {}
for bucket in probBuckets:
    resolutionByProb[bucket]={'sum': 0, 'count': 0, 'avg': 0}

for market in marketSummary.values():
    try:
        bucket=min(list(probBuckets), key=lambda x:abs(x-market['avgProb'])) # get closest bucket
        if market['resolution'] == 'YES':
            resolutionByProb[bucket]['sum']+=1
            resolutionByProb[bucket]['count']+=1
            resolutionByProb[bucket]['avg']=resolutionByProb[bucket]['sum']/resolutionByProb[bucket]['count']
        elif market['resolution'] == 'NO':
            resolutionByProb[bucket]['count']+=1
            resolutionByProb[bucket]['avg']=resolutionByProb[bucket]['sum']/resolutionByProb[bucket]['count']
    except KeyError:
        pass

refpoint=max(list(resolutionByProb[bucket]['count'] for bucket in probBuckets))

fig = go.Figure()
fig.add_trace(go.Scatter(
    name='All Markets',
    x=list(resolutionByProb.keys()),
    y=list(round(resolutionByProb[bucket]['avg'],3) for bucket in probBuckets),
    mode='markers',
    marker=dict(
        size=list(resolutionByProb[bucket]['count']/refpoint*100 for bucket in probBuckets),
        sizemin=3,
        color=list(resolutionByProb[bucket]['count'] for bucket in probBuckets),
        #colorbar_title='Count',
        colorscale='greens',
        cmin=-0.25*refpoint,
        cmax=0.75*refpoint
    )
))
fig.add_shape(
    type="line",
    x0=0, y0=0, x1=1, y1=1
)
fig.update_layout(
    title_text='Calibration Plot: Binary-Resolved Markets by Historical Probability',
    xaxis_title_text='Historical Probability, time-weigthed',
    yaxis_title_text='Resolution',
)
fig.layout.xaxis.tickformat = ',.0%'
fig.layout.yaxis.tickformat = ',.0%'
fig.update_xaxes(range=[0,1])
fig.update_yaxes(range=[0,1])
fig.show()


# > The problem with the previous graph is the fact that we don't usually care about markets after they're closed! We want to know how accurate those markets were while things were still uncertain. 
# In order to do that we take a time-weighted average of all bets, which means that if a market was sitting at around 30% for the bulk of the time and suddenly shifted to 99% as some news came in, it gets sorted into the 30% bucket instead of the 99% one. The markets with the most activity (largest circles) seem to follow the line pretty well!

# ## Brier Scores

# In[33]:


chartLabels = {
    'brierScore': 'Brier Score',
}

chartData = {}
for prop in chartLabels:
    chartData[prop]=[]
    for market in marketSummary.values():
        try:
            chartData[prop].append(market[prop])
        except:
            pass

fig = go.Figure()
for prop in chartLabels:
    fig.add_trace(go.Histogram(
        x=chartData[prop],
        name=chartLabels[prop],
    ))
fig.update_traces(
    xbins_size=0.005,
    xbins_start=0,
    xbins_end=1
)
fig.update_layout(
    title_text='Histogram: Brier Scores',
    xaxis_title_text='Brier Score',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[0,1])
fig.add_annotation(
    x=0.25, y=0,
    ax=0, ay=-75,
    text='Random Chance',
    xanchor='left'
)
fig.add_annotation(
    x=0.15, y=0,
    ax=0, ay=-100,
    text='Metaculus Community',
    xanchor='left'
)
fig.add_annotation(
    x=statistics.median(chartData['brierScore']), y=0,
    ax=0, ay=-125,
    text='Manifold Median',
    xanchor='left'
)
fig.add_annotation(
    x=0.075, y=0,
    ax=0, ay=-150,
    text='Excellent Predictors',
    xanchor='left'
)
fig.show()


# In[34]:


lookbackBins = lookbackBinsStd
tableSubject='Brier Score'
tableHeaders=['Markets resolved in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['Number of Markets in sample'],
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    scoresList = []
    for market in marketSummary.values():
        try:
            if market['resolutionTime'] > datetime.today() - timedelta(days=lookbackTime) and not market['brierScore'] == None:
                scoresList.append(market['brierScore'])
        except KeyError:
            pass
    try:
        tableData[0].append(len(scoresList))
        tableData[1].append(round(numpy.percentile(scoresList,5),4))
        tableData[2].append(round(statistics.mean(scoresList),4))
        tableData[3].append(round(statistics.median(scoresList),4))
        tableData[4].append(round(numpy.percentile(scoresList,95),4))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')
        tableData[4].append('N/A')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > The calibration plots above are great for seeing how we deal with uncertainty over a range, but what if there was a numeric score for how "close" any market is to the right answer? Good news, there is! Brier scores are basically a mean squared error for how close we were to the right answer (that means lower is better). If we take the "average historal probability" from above and check how close that was to the resolution value, we see most of our markets were pretty close! A "true random" guess on every market would yield a Brier score of 0.25, so most of our markets are better than random chance (phew).

# In[35]:


valueBuckets = [0,20,40,60,80,
               100,120,140,160,180,
               200,220,240,260,280,
               300,320,340,360,380,
               400,420,440,460,480,
               500,550,600,650,700,
               750,800,850,900,950,
               1000,1100,1200,1300,
               1400,1500,1600,1700,
               1800,1900,
               2000,2200,2400,2600,
               2800,3000,3200,3400,
               3600,3800,4000,4200,
               4400,4600,4800,5000,
               5500,6000,6500,7000,
               7500,8000,8500,9000,
               10000,12000,14000,16000,18000,
               20000,25000,30000,40000,50000]

brierScoreByValue = {}
for bucket in valueBuckets:
    brierScoreByValue[bucket]={'sum': 0, 'count': 0, 'avg': 0}

for market in marketSummary.values():
    try:
        bucket=min(list(valueBuckets), key=lambda x:abs(x-market['volume']))
        brierScoreByValue[bucket]['sum']+=market['brierScore']
        brierScoreByValue[bucket]['count']+=1
        brierScoreByValue[bucket]['avg']=brierScoreByValue[bucket]['sum']/brierScoreByValue[bucket]['count']
    except KeyError:
        pass
    except TypeError:
        pass

refpoint=max(list(brierScoreByValue[bucket]['count'] for bucket in valueBuckets))

fig = go.Figure()
fig.add_trace(go.Scatter(
    name='All Markets',
    x=list(brierScoreByValue.keys()),
    y=list(brierScoreByValue[bucket]['avg'] for bucket in valueBuckets),
    mode='markers',
    marker=dict(
        size=list(brierScoreByValue[bucket]['count']/refpoint*100 for bucket in valueBuckets),
        sizemin=3,
        color=list(brierScoreByValue[bucket]['count'] for bucket in valueBuckets),
        #colorbar_title='Count',
        colorscale='OrRd',
        cmin=-0.75*refpoint,
        cmax=0.85*refpoint
    )
))
fig.update_layout(
    title_text='Plot: Brier Score vs Market Value (Truncated)',
    xaxis_title_text='M$',
    yaxis_title_text='Brier Score',
)
fig.update_xaxes(range=[0,2500])
fig.update_yaxes(range=[0,0.4])
fig.show()


# > Hypothesis: Markets with more attention, activity, and bets are more accurate. 
# 
# > Test: Plot Brier scores from a bunch of markets and arrange them by the amount of money invested (value).
# 
# > Result: Scores tend downwards as the market value increases! Compare to the Metaculus community [prediction value](https://www.metaculus.com/questions/track-record/) of ~0.15.

# In[36]:


timeList=[]
for market in marketSummary.values():
    try:
        timeList.append(market['resolutionTime'])
    except KeyError:
        pass
t0=min(timeList)
tf=max(timeList)

timeBuckets = []
ti=t0
while True:
    timeBuckets.append(ti)
    ti+=timedelta(days=3)
    if ti > tf:
        break

brierScoreByTime = {}
for bucket in timeBuckets:
    brierScoreByTime[bucket]={'sum': 0, 'count': 0, 'avg': 0}

for market in marketSummary.values():
    try:
        bucket=min(list(timeBuckets), key=lambda x:abs(x-market['resolutionTime']))
        brierScoreByTime[bucket]['sum']+=market['brierScore']
        brierScoreByTime[bucket]['count']+=1
        brierScoreByTime[bucket]['avg']=brierScoreByTime[bucket]['sum']/brierScoreByTime[bucket]['count']
    except KeyError:
        pass
    except TypeError:
        pass

refpoint=max(list(brierScoreByTime[bucket]['count'] for bucket in timeBuckets))

fig = go.Figure()
fig.add_trace(go.Scatter(
    name='All Markets',
    x=list(brierScoreByTime.keys()),
    y=list(brierScoreByTime[bucket]['avg'] for bucket in timeBuckets),
    mode='markers',
    marker=dict(
        size=list(brierScoreByTime[bucket]['count']/refpoint*100 for bucket in timeBuckets),
        sizemin=3,
        color=list(brierScoreByTime[bucket]['count'] for bucket in timeBuckets),
        #colorbar_title='Count',
        colorscale='OrRd',
        cmin=-0.75*refpoint,
        cmax=0.85*refpoint
    )
))
fig.update_layout(
    title_text='Plot: Brier Score vs Date Resolved',
    xaxis_title_text='Date Resolved',
    yaxis_title_text='Brier Score',
)
fig.update_xaxes(range=[
    datetime(2022,1,1),
    timeBuckets[len(timeBuckets)-1]
])
fig.update_yaxes(range=[0,0.4])
fig.show()


# > Have we gotten more accurate over time? Analysis TBD.

# ## Users, Bets and Comments

# In[37]:


betAmounts = []
for market in marketsFull:
    for bet in market['bets']:
        try:
            betAmounts.append(abs(bet['amount']))
        except TypeError:
            pass

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=betAmounts,
    marker_color='rgba(40,100,140,0.8)'
))
fig.update_traces(
    xbins_size=5,
    xbins_start=0,
    xbins_end=100000
)
fig.update_layout(
    title_text='Histogram: Individual Bet Amounts',
    xaxis_title_text='Markets',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[0,1000])
fig.add_annotation(
    x=numpy.percentile(betAmounts,95), y=0,
    ax=0, ay=-50,
    text='95th Percentile',
    xanchor='left',
)
fig.show()


# In[38]:


get_ipython().run_cell_magic('capture', '', "timeList=[]\nfor bet in betSummary.values():\n    try:\n        timeList.append(bet['createdTime'])\n    except KeyError:\n        pass\nt0=min(timeList)\ntf=max(timeList)\n\ntimeBuckets = []\nti=t0\nwhile True:\n    timeBuckets.append(ti)\n    ti+=timedelta(days=7)\n    if ti > tf:\n        break\n\nmedianBetByTime = {}\nfor bucket in timeBuckets:\n    medianBetByTime[bucket]={'values': []}\n\nfor bet in betSummary.values():\n    bucket=min(list(timeBuckets), key=lambda x:abs(x-bet['createdTime']))\n    medianBetByTime[bucket]['values'].append(bet['amount'])\n\nfor bucket in timeBuckets:\n    medianBetByTime[bucket]['avg']=statistics.mean(medianBetByTime[bucket]['values'])\n    medianBetByTime[bucket]['median']=statistics.median(medianBetByTime[bucket]['values'])\n\nfig = go.Figure()\n\nrefpoint=max(list(len(medianBetByTime[bucket]['values']) for bucket in timeBuckets))\nfig.add_trace(go.Scatter(\n    name='Average Bet',\n    x=list(medianBetByTime.keys()),\n    y=list(medianBetByTime[bucket]['avg'] for bucket in timeBuckets),\n    mode='markers',\n    marker=dict(\n        size=list(len(medianBetByTime[bucket]['values'])/refpoint*100 for bucket in timeBuckets),\n        sizemin=3,\n        color=list(len(medianBetByTime[bucket]['values']) for bucket in timeBuckets),\n        #colorbar_title='Count',\n        colorscale='PuRd',\n        cmin=-0.75*refpoint,\n        cmax=0.85*refpoint\n    )\n))\nfig.add_trace(go.Scatter(\n    name='Median Bet',\n    x=list(medianBetByTime.keys()),\n    y=list(medianBetByTime[bucket]['median'] for bucket in timeBuckets),\n    mode='markers',\n    marker=dict(\n        size=list(len(medianBetByTime[bucket]['values'])/refpoint*100 for bucket in timeBuckets),\n        sizemin=3,\n        color=list(len(medianBetByTime[bucket]['values']) for bucket in timeBuckets),\n        #olorbar_title='Count',\n        colorscale='OrRd',\n        cmin=-0.75*refpoint,\n        cmax=0.85*refpoint\n    )\n))\nfig.update_layout(\n    title_text='Plot: Bet Amounts over Time',\n    xaxis_title_text='Date',\n    yaxis_title_text='Bet Amount',\n)\n#fig.update_xaxes(range=[0,2500])\nfig.update_yaxes(range=[\n    0,\n    max([\n        max(medianBetByTime[bucket]['avg'] for bucket in timeBuckets),\n        max(medianBetByTime[bucket]['median'] for bucket in timeBuckets),\n    ])*1.25])\nfig.show()\n")


# In[39]:


lookbackBins = lookbackBinsStd
tableSubject='Bet Amount'
tableHeaders=['Bets placed in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['Number of Bets'],
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    itemList = []
    for market in marketsFull:
        for bet in market['bets']:
            try:
                if bet['createdTime']/1000 > (datetime.today()-timedelta(days=lookbackTime)).timestamp() and abs(bet['amount']) >= 1:
                    itemList.append(abs(bet['amount']))
            except TypeError:
                pass
    try:
        tableData[0].append(len(itemList))
        tableData[1].append(round(numpy.percentile(itemList,5),2))
        tableData[2].append(round(statistics.mean(itemList),2))
        tableData[3].append(round(statistics.median(itemList),2))
        tableData[4].append(round(numpy.percentile(itemList,95),4))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')
        tableData[4].append('N/A')

tableHeaders.append('')
for i in range(len(tableData)):
    tableData[i].append('M$')
tableData[0][len(tableData)]='bets'

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# > How much do you bet at once? 
# There are some natural schelling points but the introduction of quick bets seems to have shaken things up!

# In[40]:


chartLabels = {
    'numComments': 'Number of Comments',
}

chartData = {}
for prop in chartLabels:
    chartData[prop]=[]
    for market in marketSummary.values():
        try:
            chartData[prop].append(market[prop])
        except:
            pass

fig = go.Figure()
for prop in chartLabels:
    fig.add_trace(go.Histogram(
        x=chartData[prop],
        name=chartLabels[prop],
        marker_color='rgba(0,140,100,1)',
    ))
fig.update_traces(
    xbins_size=1,
    #xbins_start=0,
    #xbins_end=10000
)
fig.update_layout(
    title_text='Histogram: Number of Comments',
    xaxis_title_text='Number of Comments',
    yaxis_title_text='Count', 
    bargap=0.1
)
fig.update_xaxes(range=[-0.5,50])
fig.add_annotation(
    x=statistics.median(chartData['numComments']), y=0,
    ax=0, ay=-100,
    text='Median',
    xanchor='left',
    bgcolor='white', opacity=0.95
)
fig.add_annotation(
    x=numpy.percentile(chartData['numComments'],95), y=0,
    ax=0, ay=-50,
    text='95th Percentile',
    xanchor='left',
)
fig.show()


# In[41]:


lookbackBins = lookbackBinsStd
tableSubject='Number of Comments'
tableHeaders=['Markets created in the past...']
[tableHeaders.append(i) for i in lookbackBins.keys()]

tableData=[
    ['Number of Markets in sample'],
    ['5th Percentile ' + tableSubject],
    ['Average ' + tableSubject],
    ['Median ' + tableSubject],
    ['95th Percentile ' + tableSubject],
]

for lookbackTime in lookbackBins.values():
    scoresList = []
    for market in marketSummary.values():
        try:
            if market['createdTime'] > datetime.today() - timedelta(days=lookbackTime):
                scoresList.append(market['numComments'])
        except KeyError:
            pass
    try:
        tableData[0].append(len(scoresList))
        tableData[1].append(round(numpy.percentile(scoresList,5),1))
        tableData[2].append(round(statistics.mean(scoresList),1))
        tableData[3].append(round(statistics.median(scoresList),1))
        tableData[4].append(round(numpy.percentile(scoresList,95),1))
    except IndexError:
        tableData[0].append('N/A')
        tableData[1].append('N/A')
        tableData[2].append('N/A')
        tableData[3].append('N/A')
        tableData[4].append('N/A')

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='html'
)
table


# In[42]:


usersBreakdown = {}
for market in marketSummary.values():
    try:
        usersBreakdown[market['creatorUsername']] += 1
    except KeyError:
        usersBreakdown[market['creatorUsername']] = 1

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=list(usersBreakdown.values()),
    marker_color='rgba(40,40,40,0.8)'
))
fig.update_traces(
    xbins_size=1
)
fig.update_layout(
    title_text='Histogram: Markets Created per User',
    xaxis_title_text='Markets',
    yaxis_title_text='Count',
    bargap=0.1,
    bargroupgap=0
)
fig.add_annotation(
    x=numpy.percentile(list(usersBreakdown.values()),95), y=0,
    ax=0, ay=-50,
    text='95th Percentile',
    xanchor='left',
)
fig.show()


# > I'm not at all surprised most users only make a few markets. 
# I'm actually surprised how short the tail is, I would have expected the max to be well over 500 or so.
# I think a large bulge will slowly move to the right as long as the daily free markets are active.

# In[43]:


betAmounts = []
for bettor in bettorSummary.values():
    betAmounts.append(bettor['betAmountTotal'])

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=betAmounts,
    marker_color='rgba(40,40,40,0.8)'
))
fig.update_traces(
    xbins_size=10,
    xbins_start=-5000,
    xbins_end=100000
)
fig.update_layout(
    title_text='Histogram: Total Amount Bet per User',
    xaxis_title_text='M$',
    yaxis_title_text='Count',
    bargap=0.1
)
fig.update_xaxes(range=[0,5000])
fig.add_annotation(
    x=statistics.median(betAmounts), y=0,
    ax=0, ay=-50,
    text='Median',
    xanchor='left',
)
fig.add_annotation(
    x=numpy.percentile(betAmounts,75), y=0,
    ax=0, ay=-50,
    text='75th Percentile',
    xanchor='left',
)
fig.show()


# > It still looks like a lot of people bet their entire starting balance and leave. Maybe we should have some sort of daily login bonus?

# In[44]:


get_ipython().run_cell_magic('capture', '', "chartLabels = {\n    'balance': 'Actual Balance',\n    'calculatedBalance': 'Calculated Balance'\n}\n\nchartData = {}\nfor prop in chartLabels:\n    chartData[prop]=[]\n    for user in userSummary.values():\n        try:\n            chartData[prop].append(user[prop])\n        except:\n            pass\n\nfig = go.Figure()\nfor prop in chartLabels:\n    fig.add_trace(go.Histogram(\n        x=chartData[prop],\n        name=chartLabels[prop],\n    ))\nfig.update_traces(\n    xbins_size=50,\n    xbins_start=0,\n    xbins_end=10000\n)\nfig.update_layout(\n    title_text='Histogram: User Balance',\n    xaxis_title_text='M$',\n    yaxis_title_text='Count',\n    bargap=0.1\n)\nfig.update_xaxes(range=[0,5000])\nfig.add_annotation(\n    x=statistics.median(chartData['balance']), y=0,\n    ax=0, ay=-100,\n    text='Median Balance',\n    xanchor='right'\n)\nfig.add_annotation(\n    x=numpy.percentile(chartData['balance'],95), y=0,\n    ax=0, ay=-75,\n    text='95th Percentile',\n    xanchor='left'\n)\nfig.show()\n")


# In[45]:


get_ipython().run_cell_magic('capture', '', "lookbackBins = lookbackBinsStd\ntableSubject='Balance'\ntableHeaders=['Users registered in the past...']\n[tableHeaders.append(i) for i in lookbackBins.keys()]\n\ntableData=[\n    ['Number of Users'],\n    ['5th Percentile ' + tableSubject],\n    ['Average ' + tableSubject],\n    ['Median ' + tableSubject],\n    ['95th Percentile ' + tableSubject],\n]\n\nfor lookbackTime in lookbackBins.values():\n    itemList = []\n    for user in userSummary.values():\n        if user['createdTime'] > (datetime.today() - timedelta(days=lookbackTime)):\n            itemList.append(user['balance'])\n    if len(itemList) > 0:\n        tableData[0].append(len(itemList))\n        tableData[1].append(round(numpy.percentile(itemList,5)))\n        tableData[2].append(round(statistics.mean(itemList)))\n        tableData[3].append(round(statistics.median(itemList)))\n        tableData[4].append(round(numpy.percentile(itemList,95)))\n    else:\n        tableData[0].append(0)\n        tableData[1].append('N/A')\n        tableData[2].append('N/A')\n        tableData[3].append('N/A')\n        tableData[4].append('N/A')\n\ntableHeaders.append('')\nfor i in range(len(tableData)):\n    tableData[i].append('M$')\ntableData[0][len(tableData)]='users'\n\ntable = tabulate.tabulate(\n    tableData,\n    headers=tableHeaders,\n    tablefmt='html'\n)\ntable\n")


# In[46]:


get_ipython().run_cell_magic('capture', '', "tableHeaders=[\n    'Median Error',\n    '95th Percentile',\n    'Total Error'\n]\n\ntableData=[[\n    'M$ ' + str(\n        round(statistics.median( [abs(user['calculatedBalance']-user['balance']) for user in userSummary.values()] ),2)\n    ),\n    'M$ ' + str(\n        round(numpy.percentile( [abs(user['calculatedBalance']-user['balance']) for user in userSummary.values()],95 ),2)\n    ),\n    str(\n        100*abs(round( \n            (\n                sum([user['balance'] for user in userSummary.values()]) - \n                sum([user['calculatedBalance'] for user in userSummary.values()]) \n            ) / sum([user['balance'] for user in userSummary.values()]),2))\n    ) + '%',\n]]\n\ntable = tabulate.tabulate(\n    tableData,\n    headers=tableHeaders,\n    tablefmt='html'\n)\ntable\n")


# ## Economy

# In[47]:


timeList=[]
for bet in betSummary.values():
    try:
        timeList.append(bet['createdTime'])
    except KeyError:
        pass
t0=min(timeList)
tf=max(timeList)

timeBuckets = []
ti=t0
while True:
    timeBuckets.append(ti)
    ti+=timedelta(days=1)
    if ti > tf:
        break

loansByTime = {}
for bucket in timeBuckets:
    loansByTime[bucket]={'loaned': 0, 'returned': 0}
    for bet in betSummary.values():
        try:
            if bet['createdTime'] < bucket and bet['loanAmount'] > 0:
                # bet made, add to total loaned
                loansByTime[bucket]['loaned']+=bet['loanAmount']
            if bet['createdTime'] < bucket and bet['loanAmount'] < 0:
                # bet sold, money returned
                loansByTime[bucket]['returned']+=bet['loanAmount']
        except KeyError:
            pass
        
        try:
            if marketSummary[bet['marketID']]['resolutionTime'] < bucket and bet['loanAmount'] > 0:
                # return all loans upon market resolution
                loansByTime[bucket]['returned']+=bet['loanAmount']
        except KeyError:
            pass

fig = go.Figure()

fig.add_trace(go.Scatter(
    name='Loaned',
    x=list(loansByTime.keys()),
    y=list(loansByTime[bucket]['loaned'] for bucket in timeBuckets),
    mode='lines',
))
fig.add_trace(go.Scatter(
    name='Returned',
    x=list(loansByTime.keys()),
    y=list(loansByTime[bucket]['returned'] for bucket in timeBuckets),
    mode='lines',
))
fig.add_trace(go.Scatter(
    name='Outstanding',
    x=list(loansByTime.keys()),
    y=list(loansByTime[bucket]['loaned']-loansByTime[bucket]['returned'] for bucket in timeBuckets),
    mode='lines',
))
fig.update_layout(
    title_text='Plot: Loaned Balance over Time',
    xaxis_title_text='Date',
    yaxis_title_text='M$',
)
fig.update_xaxes(range=[
    datetime(2022,3,1),
    max(loansByTime.keys())
])
fig.update_yaxes(range=[
    0,
    max(loansByTime[bucket]['loaned'] for bucket in timeBuckets)*1.25
])
fig.add_annotation(
    x=datetime(2022,4,13), 
    y=263402,
    ax=-30, ay=-10,
    text='Loans Ended',
    xanchor='right',
    showarrow=True,
    arrowhead=5,
    arrowsize=1
)
fig.show()


# > Between March and April this year, Manifold added an interesting new feature: loans! The first few bucks you bet in any market would be an interest-free loan, to be paid back at the market's resolution. For better or worse, it was widely used, with over $263,000 in total loans. Eventually the program ended, but many of those bets were in very long markets so they will be paid back after quite some time. When do you think the last loan will be repaid?

# In[48]:


timeList=[]
for bet in betSummary.values():
    try:
        timeList.append(bet['createdTime'])
    except KeyError:
        pass
t0=min(timeList)
tf=max(timeList)

timeBuckets = []
ti=t0
while True:
    timeBuckets.append(ti)
    ti+=timedelta(days=1)
    if ti > tf:
        break

flowByTime = {}
for bucket in timeBuckets:
    flowByTime[bucket]={'platformFee': 0, 'dailyFreeMarket': 0, 'newUserBalance': 0}
    for bet in betSummary.values():
        try:
            if bet['createdTime'] < bucket:
                flowByTime[bucket]['platformFee']+=bet['platformFee']
        except KeyError:
            pass

    for market in marketSummary.values():
        if market['dailyFreeMarket'] and market['createdTime'] < bucket:
            flowByTime[bucket]['dailyFreeMarket']+=100
            
    for bettor in bettorSummary.values():
        if bettor['firstBet'] < bucket:
            flowByTime[bucket]['newUserBalance']+=1000

fig = go.Figure()

fig.add_trace(go.Scatter(
    name='Injected via New User Balance',
    x=list(flowByTime.keys()),
    y=list(flowByTime[bucket]['newUserBalance'] for bucket in timeBuckets),
    mode='lines',
))
fig.add_trace(go.Scatter(
    name='Injected via Daily Free Market',
    x=list(flowByTime.keys()),
    y=list(flowByTime[bucket]['dailyFreeMarket'] for bucket in timeBuckets),
    mode='lines',
))
fig.add_trace(go.Scatter(
    name='Extracted via Fees',
    x=list(flowByTime.keys()),
    y=list(flowByTime[bucket]['platformFee'] for bucket in timeBuckets),
    mode='lines',
))
fig.update_layout(
    title_text='Plot: Mana Flow over Time',
    xaxis_title_text='Date',
    yaxis_title_text='M$ (log scale)',
)
fig.update_xaxes(
    range=[
#        min(flowByTime.keys()),
        datetime(2022,1,1),
        max(flowByTime.keys())
    ])
fig.update_yaxes(
    type='log',
    range=[2,7]
)
fig.add_annotation(
    x=datetime(2022,6,23), 
    y=5.266,
    ax=-30, ay=-10,
    text='Free Markets Ended',
    xanchor='right',
    showarrow=True,
    arrowhead=5,
    arrowsize=1
)
fig.add_annotation(
    x=datetime(2022,6,22), 
    y=3.466,
    ax=-30, ay=-10,
    text='CPMM Inflation Fees Ended',
    xanchor='right',
    showarrow=True,
    arrowhead=5,
    arrowsize=1
)
fig.show()


# > How is Manifold's economy doing? Lots of Mana is injected in, that's for sure! Fees were supposed to remove a fair bit to keep inflation low, but it wasn't really working. The good news is even if there is inflation, that's not necessarily a bad thing. As long as people keep buying and using it, Mana will continue to have value!

# In[49]:


timeList=[]
for market in marketSummary.values():
    timeList.append(market['createdTime'])
t0=min(timeList)
tf=max(timeList)

timeBuckets = []
ti=t0
while ti < tf:
    timeBuckets.append(ti)
    ti+=timedelta(days=1)

flowByTime = {}
for bucket in timeBuckets:
    flowByTime[bucket]={'isFree': 0, 'isPaid': 0, 'pctFree': 0}
    for market in marketSummary.values():
        if abs(market['createdTime'] - bucket).days < 1:
            if market['dailyFreeMarket']:
                flowByTime[bucket]['isFree']+=1
            else:
                flowByTime[bucket]['isPaid']+=1
            flowByTime[bucket]['pctFree']=flowByTime[bucket]['isFree']/(flowByTime[bucket]['isFree']+flowByTime[bucket]['isPaid'])

fig = go.Figure()
fig.add_trace(go.Bar(
    name='Free Markets',
    x=list(flowByTime.keys()),
    y=list(flowByTime[bucket]['isFree'] for bucket in timeBuckets),
))
fig.add_trace(go.Bar(
    name='Paid Markets',
    x=list(flowByTime.keys()),
    y=list(flowByTime[bucket]['isPaid'] for bucket in timeBuckets),
))
fig.add_trace(go.Scatter(
    name='Percent Free',
    x=list(flowByTime.keys()),
    y=list(100*flowByTime[bucket]['pctFree'] for bucket in timeBuckets),
    mode='lines',
))
fig.update_layout(
    title_text='Plot: Free vs Paid Market Makeup',
    xaxis_title_text='Date',
    yaxis_title_text='Number of Markets',
)
fig.update_yaxes(
    range=[0,150]
)
fig.show()


# > How many markets were subsidized by Manifold? Most of them! Surprisingly, there's not been a massive drop in markets created since then.

# In[50]:


lookbackBins = [
    {
        'label': 'Previous Month<br />(5/24-6/23)',
        'start': datetime(2022,5,24),
        'end': datetime(2022,6,23),
    },{
        'label': 'Following Month<br />(6/24-7/23)',
        'start': datetime(2022,6,24),
        'end': datetime(2022,7,23),
    },
]
tableHeaders=['']
[tableHeaders.append(lookbackBin['label']) for lookbackBin in lookbackBins]

tableData=[
    ['Free Markets Created'],
    ['Paid Markets Created'],
    ['Total Markets Created'],
]

for lookbackBin in lookbackBins:
    itemList={'isFree': 0, 'isPaid': 0, 'total': 0}
    for market in marketSummary.values():
        if (
            market['createdTime'] > lookbackBin['start'] and
            market['createdTime'] < lookbackBin['end']
        ):
            if market['dailyFreeMarket']:
                itemList['isFree']+=1
            else:
                itemList['isPaid']+=1
            itemList['total']+=1
    tableData[0].append(itemList['isFree'])
    tableData[1].append(itemList['isPaid'])
    tableData[2].append(itemList['total'])

table = tabulate.tabulate(
    tableData,
    headers=tableHeaders,
    tablefmt='unsafehtml'
)
table


# > Running numbers for [this market](https://manifold.markets/ian/what-of-new-markets-will-be-created), it looks like there will be quite a few less markets created after the free markets are discontinued.

# ### Market Creator Leaderboards

# > These are a work in progress, don't take them seriously yet!
# 
# > Manifold calculates their leaderboards off total market pool, but that value is flawed for a few reasons. Therefore I have calculated these based on total market value, the description of which you can see above.

# In[51]:


numEntries=100
properties={
    'marketsCreated': {
        'label': 'Total Markets Created',
        'sortDesc': True,
        'rounding': 0,
        'prefix': '',
    },
#    'poolTotal': {
#        'label': 'Total Market Pool',
#        'sortDesc': True,
#        'rounding': 2,
#        'prefix': 'M$',
#    },
#    'volumeTotal': {
#        'label': 'Total Market Volume',
#        'sortDesc': True,
#        'rounding': 2,
#        'prefix': 'M$',
#    },
#    'volumeTotalSerious': {
#        'label': 'Market Volume (Serious)',
#        'sortDesc': True,
#        'rounding': 0,
#        'prefix': 'M$',
#    },
    'valueTotal': {
        'label': 'Total Market Value',
        'sortDesc': True,
        'rounding': 2,
        'prefix': 'M$',
    },
#    'valueTotalSerious': {
#        'label': '"Serious" Market Value',
#        'sortDesc': True,
#        'rounding': 2,
#        'prefix': 'M$',
#    },
    'numBetsTotal': {
        'label': 'Total Market Bets',
        'sortDesc': True,
        'rounding': 0,
        'prefix': '',
    },
    'numCommentsTotal': {
        'label': 'Total Market Comments',
        'sortDesc': True,
        'rounding': 0,
        'prefix': '',
    },
    'brierScoreAvg': {
        'label': 'Average Brier Score',
        'sortDesc': False,
        'rounding': 4,
        'prefix': '',
    },
}

tableData=[]
[tableData.append([i+1]) for i in range(numEntries)]

for prop in properties.keys():
    if properties[prop]['sortDesc']:
        creatorsSorted = dict(sorted(creatorSummary.items(), key = lambda x: x[1][prop], reverse=True))
    else:
        creatorsSorted = dict(sorted(creatorSummary.items(), key = lambda x: x[1][prop]))
    for i in range(numEntries):
        user=list(creatorsSorted)[i]
        tableData[i].append(
            user + 
            ' (' + 
            properties[prop]['prefix'] + 
            str(round( creatorSummary[user][prop], properties[prop]['rounding'] )) + 
            ')'
        )

table = tabulate.tabulate(
    tableData,
    headers=[prop['label'] for prop in properties.values()],
    tablefmt='html'
)
table


# ### Bettor Leaderboards

# In[52]:


numEntries=50
properties={
    'betAmountTotal': {
        'label': 'Total Amount Bet',
        'sortDesc': True,
        'rounding': 2,
        'prefix': 'M$',
    },
    'numBets': {
        'label': 'Total Number of Bets',
        'sortDesc': True,
        'rounding': 0,
        'prefix': '',
    },
}

tableData=[]
[tableData.append([i+1]) for i in range(numEntries)]

for prop in properties.keys():
    if properties[prop]['sortDesc']:
        bettorsSorted = dict(sorted(bettorSummary.items(), key = lambda x: x[1][prop], reverse=True))
    else:
        bettorsSorted = dict(sorted(bettorSummary.items(), key = lambda x: x[1][prop]))
    for i in range(numEntries):
        user=list(bettorsSorted)[i]
        tableData[i].append(
            bettorSummary[user]['bettorUsername'] + 
            ' (' + 
            properties[prop]['prefix'] + 
            str(round( bettorSummary[user][prop], properties[prop]['rounding'] )) + 
            ')'
        )

table = tabulate.tabulate(
    tableData,
    headers=[prop['label'] for prop in properties.values()],
    tablefmt='html'
)
table


# In[53]:


get_ipython().run_cell_magic('capture', '', "numEntries=50\nproperties={\n    'balance': {\n        'label': 'Total Balance',\n        'sortDesc': True,\n        'rounding': 2,\n        'prefix': 'M$',\n    },\n}\n\ntableData=[]\n[tableData.append([i+1]) for i in range(numEntries)]\n\nfor prop in properties.keys():\n    if properties[prop]['sortDesc']:\n        usersSorted = dict(sorted(userSummary.items(), key = lambda x: x[1][prop], reverse=True))\n    else:\n        usersSorted = dict(sorted(userSummary.items(), key = lambda x: x[1][prop]))\n    for i in range(numEntries):\n        user=list(usersSorted)[i]\n        tableData[i].append(\n            userSummary[user]['username'] + \n            ' (' + \n            properties[prop]['prefix'] + \n            str(round( userSummary[user][prop], properties[prop]['rounding'] )) + \n            ')'\n        )\n\ntable = tabulate.tabulate(\n    tableData,\n    headers=[prop['label'] for prop in properties.values()],\n    tablefmt='html'\n)\ntable\n")


# ### Interesting Markets

# In[54]:


numItems=10
tableSubject=str(numItems) + ' Random Markets in Need of Love'
itemList=[]
for market in marketSummary.values():
    if (
        market['isOpen'] and 
        market['numBets'] < 5
    ):
        itemList.append(market)

tableData=[]
for i in range(numItems):
    market=itemList.pop(randrange(len(itemList)))
    tableData.append(['<a href="' + market['url'] + '">' + market['question'] + '</a>'])

table = tabulate.tabulate(
    tableData,
    headers=[tableSubject],
    tablefmt='unsafehtml',
    colalign=('center',)
)
table


# In[55]:


get_ipython().run_cell_magic('capture', '', 'numItems=10\ntableSubject=str(numItems) + \' Unresolved Markets\'\nitemList=[]\nfor market in marketSummary.values():\n    if (\n        not market[\'isOpen\'] and \n        not market[\'isResolved\']\n    ):\n        itemList.append(market)\n\ntableData=[]\nfor i in range(numItems):\n    market=itemList.pop(randrange(len(itemList)))\n    tableData.append([\'<a href="\' + market[\'url\'] + \'">\' + market[\'question\'] + \'</a>\'])\n\ntable = tabulate.tabulate(\n    tableData,\n    headers=[tableSubject],\n    tablefmt=\'unsafehtml\',\n    colalign=(\'center\',)\n)\ntable\n')


# Found an error? Interested in more stats? Wanna chat? Ping me on the manifold markets [discord server](https://discord.gg/eHQBNBqXuh) and let me know!
# 
# Want the source to this page? It's a [jupyter notebook](https://wasabipesto.com/jupyter/manifold/Manifold.ipynb).

# In[56]:


print('This page was last updated ' + str(datetime.now()))


# In[57]:


scriptTime.update({'notebookEnded': datetime.now()})
print('It took ' + 
    str(round((scriptTime['notebookEnded']-scriptTime['notebookStarted']).seconds/60)) + 
    'm to execute this notebook. ' + 
    str(round((scriptTime['apiEnded']-scriptTime['apiStarted'])/(scriptTime['notebookEnded']-scriptTime['notebookStarted'])*100,2)) + 
    '% of that time was spent waiting for API calls.'
)


# In[ ]:




