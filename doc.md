# binaryWSS
very stupid websocket-based server

All messages are sent through 'channels'. A channel is a string that is used to identify a group of clients.
Each client can only be in one channel at a time.

Sending a zero-width space `u+200b` as the first character of a message will cause the server to interpret it as a
command.

Lua users: send in *binary mode* and `binary on` to avoid encoding confusion.

## Commands
*Zero width space is represented with `<ZWSP>`*

### Join / switch to a channel
`<ZWSP>join <channel>`
Enter a channel. If the channel does not exist, it will be created.

response example:
`<ZWSP>JOIN <channel>`

### Leave the current channel
`<ZWSP>leave`

response example:
`<ZWSP>LEFT`

### Get the current channel
`<ZWSP>where`

response example:
`<ZWSP>CURRENT channelName`

### Go to a random channel
`<ZWSP>random`

response example:
```
<ZWSP>LEFT
... other standard join responses ...
<ZWSP>RANDOMIZED <channel that you are now in>
```

### No-op
`<ZWSP>pass`

(no response)

### Turn on binary responses
`<ZWSP>binary on`

IMPLEMENTATION NOTE: there is no way to turn this off without reconnecting.

response example:
`<ZWSP>BINARY ON`
