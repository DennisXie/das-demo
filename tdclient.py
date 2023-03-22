import queue
import time
from typing import Callable
from openctp import thosttraderapi as tdapi


class UserConfig(object):

    brokerId: str = ""
    userId: str = ""
    password: str = ""
    appId: str = ""
    authCode: str = ""

    def __init__(self, brokerId: str, userId: str, password: str, appId: str, authCode: str):
        self.brokerId = brokerId
        self.userId = userId
        self.password = password
        self.appId = appId
        self.authCode = authCode
    
    def __str__(self) -> str:
        return f"{self.brokerId}, {self.userId}, {self.password}, {self.appId}, {self.authCode}"


class TdClient(tdapi.CThostFtdcTraderSpi):
    def __init__(self, userConfig: UserConfig = None, front: str = None):
        super().__init__()
        self.tdapi: tdapi.CThostFtdcTraderApi = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi("userId")
        self.userConfig = userConfig
        self.front: str = front or "tcp://180.168.146.187:10201"
        self.__reqId: int = 0
        self.__ready: bool = False
        self.__error: bool = False
        self.__confirmed: bool = True
        self.__queue: queue.Queue = queue.Queue()
        self.__orderCallback: Callable[[dict[str, any]], None] = None
        self.__tradeCallback: Callable[[dict[str, any]], None] = None
    
    def setUserConfig(self, userConfig: UserConfig) -> None:
        self.userConfig = userConfig

    def setFront(self, front: str) -> None:
        self.front = front

    @property
    def reqId(self) -> int:
        self.__reqId += 1
        return self.__reqId

    @property
    def ready(self) -> bool:
        return self.__ready
    
    @property
    def confirmed(self) -> bool:
        return self.__confirmed

    @property
    def error(self) -> bool:
        return self.__error

    def registerOrderCallback(self, callback: Callable[[dict[str, any]], None]) -> None:
        self.__orderCallback = callback
    
    def registerTrdeCallback(self, callback: Callable[[dict[str, any]], None]) -> None:
        self.__tradeCallback = callback

    def connect(self):
        self.tdapi.RegisterSpi(self)
        self.tdapi.SubscribePrivateTopic(tdapi.THOST_TERT_QUICK)
        self.tdapi.SubscribePublicTopic(tdapi.THOST_TERT_QUICK)
        self.tdapi.RegisterFront(self.front)
        self.tdapi.Init()
        while not self.__ready and not self.__error:
            time.sleep(0.2)

    def OnFrontConnected(self):
        """called when connect success"""
        print("OnFrontConnected")
        self.authenticate()

    def OnFrontDisconnected(self, nReason):
        """called when connection broken"""
        print(f"Front disconnect, error_code={nReason}")

    def authenticate(self):
        req = tdapi.CThostFtdcReqAuthenticateField()
        print(self.userConfig)
        req.BrokerID = self.userConfig.brokerId
        req.UserID = self.userConfig.userId
        req.AppID = self.userConfig.appId
        req.AuthCode = self.userConfig.authCode
        self.tdapi.ReqAuthenticate(req, self.reqId)

    def OnRspAuthenticate(self, pRspAuthenticateField: tdapi.CThostFtdcRspAuthenticateField,
                          pRspInfo: tdapi.CThostFtdcRspInfoField, nRequestID: int, bIsLast: bool):
        """called when authenticate success"""
        if pRspInfo is not None:
            print(f"authenticate failed, ErrorID: {pRspInfo.ErrorID}, ErrorMsg: {pRspInfo.ErrorMsg}")

        if pRspInfo is None or pRspInfo.ErrorID == 0:
            self.login()
        else:
            self.__error = True
            print("authenticate failed, please try again")

    def login(self):
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self.userConfig.brokerId
        req.UserID = self.userConfig.userId
        req.Password = self.userConfig.password
        print(f"{req.BrokerID} {req.UserID} {req.Password}")
        req.UserProductInfo = "openctp"
        self.tdapi.ReqUserLogin(req, self.reqId)

    def OnRspUserLogin(self, pRspUserLogin: tdapi.CThostFtdcRspUserLoginField, pRspInfo: tdapi.CThostFtdcRspInfoField,
                       nRequestID: int, bIsLast: bool):
        """called when login responds"""
        if pRspInfo is not None:
            print(f"login failed, ErrorID: {pRspInfo.ErrorID}, ErrorMsg: {pRspInfo.ErrorMsg}")

        if pRspInfo is None or pRspInfo.ErrorID == 0:
            self.__ready = True
            self.__today = pRspUserLogin.TradingDay
        else:
            self.__error = True
            print("login failed, please try again")
    
    def disconnect(self):
        self.tdapi.Release()
    
    def OnRtnOrder(self, pOrder: tdapi.CThostFtdcOrderField):
        if self.__orderCallback:
            data = {
                "order_local_id": pOrder.OrderLocalID,
                "trade_no": pOrder.SequenceNo,
                "account_id": pOrder.AccountID,
                "exchange_id": pOrder.ExchangeInstID,
                "instrument_id": pOrder.InstrumentID,
                "volume": pOrder.VolumeTotal,
                "volume_traded": pOrder.VolumeTraded,
                "direction": pOrder.Direction,
                "limit_price": pOrder.LimitPrice
            }
            self.__orderCallback(data)
    
    def OnRtnTrade(self, pTrade: tdapi.CThostFtdcTradeField):
        if self.__tradeCallback:
            data = {
                "client_id": pTrade.ClientID,
                "direction": pTrade.Direction,
                "volume": pTrade.Volume,
                "price": pTrade.Price,
                "instrument_id": pTrade.InstrumentID,
                "exchange_id": pTrade.ExchangeID,
                "trade_id": pTrade.TradeID,
                "order_local_id": pTrade.OrderLocalID,
            }
            self.__tradeCallback(data)
