from agent.TradingAgent import TradingAgent
import pandas as pd
import numpy as np
from math import floor


class WbrAgent(TradingAgent):
    """
    Simple Trading Agent that performs Wbr portfolio rebalancing action
    """

    def __init__(self, id, name, type, symbol, starting_cash=10000000,
                 wake_up_freq='40s',
                 subscribe=False, log_orders=False, random_state=None, w=0.20, b=0.05):

        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)
        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.subscribe = subscribe  # Flag to determine whether to subscribe to data or use polling mechanism
        self.subscription_requested = False
        self.log_orders = log_orders
        self.state = "AWAITING_WAKEUP"
        self.weigth = w
        self.band = b
        self.traded = False
        self.holdings[symbol] = 0
        self.can_trade = True

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
        """ Wbr agent actions are determined after obtaining the best bid and ask in the LOB """
        super().receiveMessage(currentTime, msg)
        if msg.body['msg'] == "ORDER_EXECUTED":
            self.can_trade = True

        if msg.body['msg'] == "ORDER_CANCELLED":
            self.can_trade = True


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
        """ Wbr Agent actions logic """
        #if (not self.traded) and (self.weigth > 0) and bid and ask:
        #    quantity = floor(self.starting_cash * self.weigth / self.getCurrentMidPrice(bid, ask))
        #    self.placeMarketOrder(self.symbol, quantity, True, ignore_risk=False)
        #    self.traded = True
        if bid and ask and self.can_trade:
            midpoint = self.getCurrentMidPrice(bid, ask)
            #print(midpoint)

            # total assets total value of shares + cash
            TA = self.markToMarket(self.holdings)
            shareValue = TA - self.holdings['CASH']
            # shareToMoneyRatio is strictly less then 1
            shareToMoneyRatio = shareValue / TA
            #print("shareMoneyTo ratio "+str(shareToMoneyRatio) )
            # Wbr strategy if shareToMoney is in between then stop here
            #if (self.weigth - self.band < shareToMoneyRatio) and (shareToMoneyRatio < self.weigth + self.band):
            #    return



            if shareToMoneyRatio < (self.weigth - self.band):
                #hard to see but it should be correct solve equation (current_quantity + new quantity)* midpoint = sum(money + share) * weigth
                quantity = floor(self.weigth * TA / midpoint) - self.holdings[self.symbol]
               #print("quantity " + str(quantity))
                # it is true that is a buy order for that quantity
                symb = self.symbol
                if self.checkLiquidity(quantity, buy=True, symbol=symb):
                    self.placeMarketOrder(self.symbol, quantity, True, ignore_risk=False)
                    self.can_trade = False

            elif shareToMoneyRatio > (self.weigth + self.band):
                #should always be negative
                quantity = abs(floor((self.weigth * TA / midpoint)) - self.holdings[self.symbol])
                #self.holdings[self.symbol] = TA
                if self.checkLiquidity(quantity, buy=False, symbol=self.symbol):
                    self.placeMarketOrder(self.symbol, quantity, False)
                    self.can_trade = False

    def checkLiquidity(self, quantity, buy, symbol):
        if quantity > 0:
            # Test if this order can be permitted given our at-risk limits.
            new_holdings = self.holdings.copy()

            q = quantity if buy else -quantity

            if symbol in new_holdings:
                new_holdings[symbol] += q
            else:
                new_holdings[symbol] = q

            #cannot sell what we do not have
            if new_holdings[symbol] < 0:
                return False

            # Compute before and after at-risk capital.
            cost = self.markToMarket(new_holdings) - self.markToMarket(self.holdings)
            return self.holdings['CASH'] - cost >= 0
        else:
            return False




    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    @staticmethod
    def ma(a, n=20):
        ret = np.cumsum(a, dtype=float)
        ret[n:] = ret[n:] - ret[:-n]
        return ret[n - 1:] / n
