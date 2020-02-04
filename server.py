import asyncio
import sys
from datetime import datetime, timedelta

import configargparse
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from grpclib.server import Server, Stream
from grpclib.utils import graceful_exit
from ib_insync import IB, Stock
from ibbridge_grpc import IbLoaderBase
from ibbridge_pb2 import Bar, GetStockHistoricalDataRequest


def timestamp_from_datetime(dt):
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


def duration_from_timedelta(delta):
    dr = Duration()
    dr.FromTimedelta(delta)
    return dr


class IbLoaderServer(IbLoaderBase):
    def __init__(self, ib):
        self.ib = ib

    async def GetStockHistoricalData(
        self, stream: Stream[GetStockHistoricalDataRequest, Bar]
    ) -> None:
        request = await stream.recv_message()
        assert request is not None

        contract = Stock(request.symbol, request.exchange, request.currency)
        endDate = request.endDate.ToDatetime()
        if endDate == datetime(1970, 1, 1, 0, 0):
            endDate = None

        print(contract, endDate)
        while True:
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=endDate,
                durationStr="10 D",
                barSizeSetting="1 min",
                useRTH=True,
                whatToShow="TRADES",
                formatDate=2,
            )

            if not bars:
                break

            endDate = bars[0].date

            for bar in reversed(bars):
                await stream.send_message(
                    Bar(
                        timestamp=timestamp_from_datetime(bar.date),
                        duration=duration_from_timedelta(timedelta(minutes=1)),
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        trades=bar.barCount,
                        vwap=bar.average,
                    )
                )


def onDisconnected(ev):
    print("disconnected: %s", ev)
    sys.exit(1)


async def main(options):
    ib = IB()
    ib.disconnectedEvent += onDisconnected
    await ib.connectAsync(options.ib_host, options.ib_port)
    server = Server([IbLoaderServer(ib)])
    with graceful_exit([server]):
        await server.start(options.http_host, options.http_port)
        print(f"Serving on {options.http_host}:{options.http_port}")
        await server.wait_closed()
        ib.disconnectedEvent -= onDisconnected
        ib.disconnect()


if __name__ == "__main__":
    p = configargparse.ArgParser()
    p.add("--http-host", default="0.0.0.0", env_var="HTTP_HOST")
    p.add("--http-port", default="8443", env_var="HTTP_PORT", type=int)
    p.add("--ib-host", default="127.0.0.1", env_var="IB_HOST")
    p.add("--ib-port", default="4001", env_var="IB_PORT", type=int)
    options = p.parse_args()
    asyncio.run(main(options))
