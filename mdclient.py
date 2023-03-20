import time
from typing import Callable
from openctp import thostmduserapi as mdapi


class MdClient(mdapi.CThostFtdcMdSpi):
    def __init__(self, front: str | None = None):
        super().__init__()
        self.mdapi: mdapi.CThostFtdcMdApi = mdapi.CThostFtdcMdApi.CreateFtdcMdApi()
        self.front: str = front or "tcp://180.169.112.54:42213"
        self.__reqId: int = 0
        self.__ready: bool = False
        self.__callback: Callable[[mdapi.CThostFtdcDepthMarketDataField], None] = None
    
    @property
    def reqId(self) -> int:
        self.__reqId += 1
        return self.__reqId
    
    @property
    def ready(self) -> bool:
        return self.__ready
    
    def registerDepthMarketDataCallback(self, callback: Callable[[mdapi.CThostFtdcDepthMarketDataField], None]):
        self.__callback = callback
    
    def connect(self):
        self.mdapi.RegisterSpi(self)
        self.mdapi.RegisterFront(self.front)
        self.mdapi.Init()
    
    def OnFrontConnected(self):
        print("md front connected")
        self.login()
    
    def login(self):
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = ""
        req.UserID = ""
        req.Password = ""
        self.mdapi.ReqUserLogin(req, self.reqId)
    
    def OnRspUserLogin(self, pRspUserLogin: mdapi.CThostFtdcRspUserLoginField, pRspInfo: mdapi.CThostFtdcRspInfoField, nRequestID, bIsLast):
        if pRspInfo is not None:
            print(f"login response, ErrorId: {pRspInfo.ErrorID}, ErrorMsg: {pRspInfo.ErrorMsg}")
        
        if pRspInfo is None or pRspInfo.ErrorID == 0:
            print("login success")
            self.__ready = True
        else:
            # TODO: throw exception and try again
            exit(1)

    def disconnect(self):
        self.mdapi.Release()
    
    def OnFrontDisconnected(self, nReason):
        self.__ready = False
        print("md front disconnected")

    def logout(self):
        req = mdapi.CThostFtdcUserLogoutField()
        req.BrokerID = ""
        req.UserID = ""
        self.mdapi.ReqUserLogout(req, self.reqId)

    def OnRspUserLogout(self, pUserLogout, pRspInfo, nRequestID, bIsLast):
        return super().OnRspUserLogout(pUserLogout, pRspInfo, nRequestID, bIsLast)  
    
    def subscribe(self, instrumentIds: list[str]):
        print(f"subscribe ${instrumentIds}")
        r = self.mdapi.SubscribeMarketData(instrumentIds, self.reqId)
        t = 1
        while r != 0 and t <= 10:
            print(f"error code: ${r}, try again after 1 second. ${t}/10 tried")
            time.sleep(1.0)
            t += 1
            r = self.mdapi.SubscribeMarketData(instrumentIds, self.reqId)
    
    def OnRspSubMarketData(self, pSpecificInstrument: mdapi.CThostFtdcSpecificInstrumentField, pRspInfo: mdapi.CThostFtdcRspInfoField, nRequestID, bIsLast):
        if pRspInfo is not None:
            print(f"subscribe result, ErrorId: {pRspInfo.ErrorID}, ErrorMsg: {pRspInfo.ErrorMsg}")
        
        if pRspInfo is None or pRspInfo.ErrorID == 0:
            print(f"subscribe success, instrumentId={pSpecificInstrument.InstrumentID}")
    
    def OnRtnDepthMarketData(self, pDepthMarketData: mdapi.CThostFtdcDepthMarketDataField):
        data = {
            "instrument_id": pDepthMarketData.InstrumentID,
            "volume": pDepthMarketData.Volume,
            "turnover": pDepthMarketData.Turnover,
            "high": pDepthMarketData.HighestPrice,
            "low": pDepthMarketData.LowestPrice,
            "open": pDepthMarketData.OpenPrice,
            "close": pDepthMarketData.ClosePrice,
            "open_intrest": pDepthMarketData.OpenInterest,
        }
        self.__callback(data)
