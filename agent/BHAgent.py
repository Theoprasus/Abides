'''
from agent.examples.SubscriptionAgent import SubscriptionAgent
import pandas as pd
import random as rd
from math import floor
from copy import deepcopy


class BHAgent(SubscriptionAgent):
    """ AN agent that simply wake at a random frequency and place a market order investing a percentage(weight) of his cash
    """
    def __init__(self, id, name, type, symbol, starting_cash, levels = 1, subscription_freq = 10e9, log_orders=False, random_state=None, weight = 0.50):
        """  Constructor for ExampleExperimentalAgentTemplate.

        :param id: Agent's ID as set in config
        :param name: Agent's human-readable name as set in config
        :param type: Agent's human-readable type as set in config, useful for grouping agents semantically
        :param symbol: Name of asset being traded
        :param starting_cash: Dollar amount of cash agent starts with.
        :param levels: Number of levels of orderbook to subscribe to
        :param subscription_freq: Frequency of orderbook updates subscribed to (in nanoseconds)
        :param log_orders: bool to decide if agent's individual actions logged to file.
        :param random_state: numpy RandomState object from which agent derives randomness
        """
        super().__init__(id, name, type, symbol, starting_cash, levels, subscription_freq, log_orders=log_orders, random_state=random_state)
        self.traded = False
        self.current_bids = None  # subscription to market data populates this list
        self.current_asks = None  # subscription to market data populates this list
        self.weight = weight
        self.holdings[self.symbol]= 0

    def wakeup(self, currentTime):
        """ Action to be taken by agent at each wakeup.

            :param currentTime: pd.Timestamp for current simulation time
        """
        super().wakeup(currentTime)
        self.getCurrentSpread(self.symbol)
        self.setWakeup(currentTime + self.getWakeFrequency())




    def getCurrentMidPrice(self):
        """ Retrieve mid price from mid and ask.
         nice addition should return the midprice
        :return:
        """

        try:

            bid, _, ask, _ = self.getKnownBidAsk(self.symbol)

            if bid and ask:
                mid = int((ask + bid) / 2)
        except (TypeError, IndexError):
            return None

    def receiveMessage(self, currentTime, msg):
        """ Action taken when agent receives a message from the exchange

        :param currentTime: pd.Timestamp for current simulation time
        :param msg: message from exchange
        :return:

        """
        super().receiveMessage(currentTime, msg)  # receives subscription market data
        if msg.body['msg'] == 'QUERY_SPREAD' and (self.getCurrentMidPrice() is not None):
            quantity = floor(self.starting_cash * self.weight / self.getCurrentMidPrice())

            if quantity > self.holdings[self.symbol] and (quantity != self.holdings[self.symbol]):
                self.placeMarketOrder(self.symbol, quantity - self.holdings[self.symbol], True)
                #self.traded = True # not needed anymore
    def getWakeFrequency(self):
        """ Set next wakeup time for agent. """
        return pd.Timedelta(str(rd.randint(1, 10))+"min")

    def placeLimitOrder(self, quantity, is_buy_order, limit_price):
        """ Place a limit order at the exchange.
          :param quantity (int):      order quantity
          :param is_buy_order (bool): True if Buy else False
          :param limit_price: price level at which to place a limit order
          :return:
        """
        super().placeLimitOrder(self.symbol, quantity, is_buy_order, limit_price)

    def placeMarketOrder(self, quantity, is_buy_order):
        """ Place a market order at the exchange.
          :param quantity (int):      order quantity
          :param is_buy_order (bool): True if Buy else False
          :return:
        """
        super().placeMarketOrder(self.symbol, quantity, is_buy_order)

    def cancelAllOrders(self):
        """ Cancels all resting limit orders placed by the experimental agent.
        """
        for _, order in self.orders.items():
            self.cancelOrder(order)
'''
from agent.TradingAgent import TradingAgent
from util.util import log_print

from math import sqrt, floor
import numpy as np
import pandas as pd


class BHAgent(TradingAgent):

    def __init__(self, id, name, type, symbol='IBM', starting_cash=100000, log_orders=False, random_state=None, wakeup_time = None, weigth = 0.3 ):

        # Base class init.
        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)

        self.wakeup_time = wakeup_time,

        self.symbol = symbol  # symbol to trade

        # The agent uses this to track whether it has begun its strategy or is still
        # handling pre-market tasks.
        self.trading = False

        # The agent begins in its "complete" state, not waiting for
        # any special event or condition.
        self.state = 'AWAITING_WAKEUP'

        # The agent must track its previous wake time, so it knows how many time
        # units have passed.
        self.prev_wake_time = None
        self.weigth = weigth
        self.hasTraded =  False

        self.size = np.random.randint(20, 50)

    def kernelStarting(self, startTime):
        # self.kernel is set in Agent.kernelInitializing()
        # self.exchangeID is set in TradingAgent.kernelStarting()

        super().kernelStarting(startTime)

        self.oracle = self.kernel.oracle

    def kernelStopping(self):
        # Always call parent method to be safe.
        super().kernelStopping()

        # Print end of day valuation.
        H = int(round(self.getHoldings(self.symbol), -2) / 100)

        #noise trader surplus is marked to EOD
        bid, bid_vol, ask, ask_vol = self.getKnownBidAsk(self.symbol)

        if bid and ask:
            rT = int(bid + ask)/2
        else:
            rT = self.last_trade[ self.symbol ]

        # final (real) fundamental value times shares held.
        surplus = rT * H

        log_print("surplus after holdings: {}", surplus)

        # Add ending cash value and subtract starting cash value.
        surplus += self.holdings['CASH'] - self.starting_cash
        surplus = float(surplus) / self.starting_cash

        self.logEvent('FINAL_VALUATION', surplus, True)

        log_print(
            "{} final report.  Holdings {}, end cash {}, start cash {}, final fundamental {}, surplus {}",
            self.name, H, self.holdings['CASH'], self.starting_cash, rT, surplus)

        print("Final relative surplus", self.name, surplus)

    def wakeup(self, currentTime):
        # Parent class handles discovery of exchange times and market_open wakeup call.
        super().wakeup(currentTime)

        self.state = 'INACTIVE'

        if not self.mkt_open or not self.mkt_close:
            # TradingAgent handles discovery of exchange times.
            return
        else:
            if not self.trading:
                self.trading = True

                # Time to start trading!
                log_print("{} is ready to start trading now.", self.name)

        # Steady state wakeup behavior starts here.

        # If we've been told the market has closed for the day, we will only request
        # final price information, then stop.
        if self.mkt_closed and (self.symbol in self.daily_close_price):
            # Market is closed and we already got the daily close price.
            return

        if self.wakeup_time[0] >currentTime:
            self.setWakeup(self.wakeup_time[0])

        if self.mkt_closed and (not self.symbol in self.daily_close_price):
            self.getCurrentSpread(self.symbol)
            self.state = 'AWAITING_SPREAD'
            return

        if type(self) == BHAgent:
            self.getCurrentSpread(self.symbol)
            self.state = 'AWAITING_SPREAD'
        else:
            self.state = 'ACTIVE'

    def placeOrder(self):

        bid, bid_vol, ask, ask_vol = self.getKnownBidAsk(self.symbol)

        if bid and ask and (self.hasTraded == False):
            quantity = floor(self.starting_cash * self.weigth / (round((bid + ask) / 2)))

            # if quantity > self.holdings[self.symbol] and (quantity != self.holdings[self.symbol]):
            self.placeMarketOrder(self.symbol, quantity, True)
            self.hasTraded = True



    def receiveMessage(self, currentTime, msg):
        # Parent class schedules market open wakeup call once market open/close times are known.
        super().receiveMessage(currentTime, msg)

        # We have been awakened by something other than our scheduled wakeup.
        # If our internal state indicates we were waiting for a particular event,
        # check if we can transition to a new state.

        if msg.body['msg'] == "ORDER_EXECUTED":
            self.hasTraded = True

        if msg.body['msg'] == "ORDER_CANCELLED":
            self.hasTraded = False


        if self.state == 'AWAITING_SPREAD':
            # We were waiting to receive the current spread/book.  Since we don't currently
            # track timestamps on retained information, we rely on actually seeing a
            # QUERY_SPREAD response message.

            if msg.body['msg'] == 'QUERY_SPREAD':
                # This is what we were waiting for.

                # But if the market is now closed, don't advance to placing orders.
                if self.mkt_closed: return

                # We now have the information needed to place a limit order with the eta
                # strategic threshold parameter.
                self.placeOrder()
                self.state = 'AWAITING_WAKEUP'

    # Internal state and logic specific to this agent subclass.

    # Cancel all open orders.
    # Return value: did we issue any cancellation requests?
    def cancelOrders(self):
        if not self.orders: return False

        for id, order in self.orders.items():
            self.cancelOrder(order)

        return True

    def getWakeFrequency(self):
        return pd.Timedelta(self.random_state.randint(low=0, high=100), unit='ns')




