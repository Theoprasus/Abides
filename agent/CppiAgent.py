from agent.TradingAgent import TradingAgent
import pandas as pd
import numpy as np
from math import floor



class CppiAgent(TradingAgent):
    """
    Simple Trading Agent that performs cppi portfolio rebalancing action
    """

    def __init__(self, id, name, type, symbol, starting_cash = 10000000,
                wake_up_freq='60s',
                subscribe=False, log_orders=False, random_state=None, m = 1.5, f = 8000000 ):

        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)
        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.subscribe = subscribe  # Flag to determine whether to subscribe to data or use polling mechanism
        self.subscription_requested = False
        self.log_orders = log_orders
        self.state = "AWAITING_WAKEUP"
        self.mult = m
        self.floor = f

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def wakeup(self, currentTime):
        """ Agent wakeup is determined by self.wake_up_freq """
        can_trade = super().wakeup(currentTime)
        if self.subscribe and not self.subscription_requested:
            super().requestDataSubscription(self.symbol, levels=1, freq=10e9)
            self.subscription_requested = True
            self.state = 'AWAITING_MARKET_DATA'
        elif can_trade and not self.subscribe:
            self.getCurrentSpread(self.symbol)
            self.state = 'AWAITING_SPREAD'

    def receiveMessage(self, currentTime, msg):
        """ cppi agent actions are determined after obtaining the best bid and ask in the LOB """
        super().receiveMessage(currentTime, msg)
        if not self.subscribe and self.state == 'AWAITING_SPREAD' and msg.body['msg'] == 'QUERY_SPREAD':
            bid, _, ask, _ = self.getKnownBidAsk(self.symbol)
            self.placeOrders(bid, ask)
            self.setWakeup(currentTime + self.getWakeFrequency())
            self.state = 'AWAITING_WAKEUP'
        elif self.subscribe and self.state == 'AWAITING_MARKET_DATA' and msg.body['msg'] == 'MARKET_DATA':
            bids, asks = self.known_bids[self.symbol], self.known_asks[self.symbol]
            if bids and asks: self.placeOrders(bids[0][0], asks[0][0])
            self.state = 'AWAITING_MARKET_DATA'

    def getCurrentMidPrice(self, bid, ask):
        """ Retrieve mid price from mid and ask.

        :return:
        """

        try:
            best_bid = bid
            best_ask = ask
            return round((best_ask + best_bid) / 2)
        except (TypeError, IndexError):
            return None

    def placeOrders(self, bid, ask):
        """ Cppi Agent actions logic """
        if bid and ask:
            midpoint = self.getCurrentMidPrice(bid, ask)
            # investement multiplier
            M = self.mult
            # allowable floor
            F = self.floor
            # total assets total value of shares + cash
            TA = self.markToMarket(self.holdings) #- self.holdings['CASH']
            shareValue = TA - self.holdings['CASH']
            # CPPI strategy
            #should be bigger than 0 but this damned abides do magic
            MoneyToInvest = M * (TA - F)

            #bid, ask, midpoint = self.getKnownBidAskMidpoint(self.symbol)


            if (shareValue < MoneyToInvest) and (midpoint > 0) and (shareValue >= 0) and (MoneyToInvest > 0):
                quantity = floor((MoneyToInvest - shareValue) / midpoint)
                #print( "quantity : " + str(quantity) +"midpoint: "+ str(midpoint)+ "|money to invest: "+ str(MoneyToInvest) + "shareVAlue"+ str(shareValue) )
                # it is true that is a buy order for that quantity
                if (self.holdings['CASH'] - (quantity * midpoint)) >= 0:
                    self.placeMarketOrder(self.symbol, quantity, True, ignore_risk=False)

            elif (shareValue > MoneyToInvest) and (midpoint > 0) and (MoneyToInvest > 0):
                quantity = floor((shareValue - MoneyToInvest) / midpoint)
                self.placeMarketOrder(self.symbol, quantity, False, ignore_risk=False)

            elif (shareValue > MoneyToInvest) and (midpoint > 0) and (MoneyToInvest < 0) and (shareValue >0):
                #just sell everything but do not go negative
                quantity = floor(shareValue / midpoint)
                self.placeMarketOrder(self.symbol, quantity, False, ignore_risk=False)

            elif (shareValue > MoneyToInvest) and (midpoint > 0) and (MoneyToInvest < 0) and (shareValue < 0):
                # just what we do in negative situation?
                quantity = abs(floor(shareValue / midpoint))
                self.placeMarketOrder(self.symbol, quantity, True, ignore_risk=False)



    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    @staticmethod
    def ma(a, n=20):
        ret = np.cumsum(a, dtype=float)
        ret[n:] = ret[n:] - ret[:-n]
        return ret[n - 1:] / n