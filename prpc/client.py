import asyncio

from prpc.transport import MsgpackTransport


class ProtocolClient(asyncio.Protocol):
    def __init__(self, rpc_transport=MsgpackTransport):
        self.rpc_transport = rpc_transport
        self.transport = None

        self.futures = {}

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        reply = self.rpc_transport.deserialize_reply(data)
        if reply.uuid in self.futures:
            self.futures[reply.uuid].set_result(reply.obj)
            del self.futures[reply.uuid]

    def cast(self, method_name, *args, **kwargs):
        msg, _ = self.rpc_transport.serialize_call(method_name, *args, **kwargs)
        self.transport.write(msg)

    async def call(self, method_name, *args, **kwargs):
        msg, uuid = self.rpc_transport.serialize_call(method_name, *args, **kwargs)

        future = asyncio.Future()
        self.futures[uuid] = future

        # only write msg after future is registered, to avoid race
        self.transport.write(msg)

        return await future


class ClientFactory:
    def __init__(self, protocol=ProtocolClient, loop=None):
        self.loop = loop
        if not self.loop:
            self.loop = asyncio.get_event_loop()

        self.protocol = protocol

    def connect(self, host, port):
        client = self.protocol()

        connect = self.loop.create_connection(lambda: client, host, port)
        # fixme: maybe we don't actually want to do this?
        self.loop.run_until_complete(connect)

        return client