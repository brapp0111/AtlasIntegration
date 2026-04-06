2.0 TCP/UDP Overview
TCP port 5321 is used on AZM4/AZM8 for modifying parameter values, subscribing, and unsubscribing. Subscription updates for all parameters aside
from meters are sent back using the TCP port.
UDP port 3131 is used by the AZM4/AZM8 to send subscription updates for meters.
When the TCP connection is terminated by the client or AZM4/AZM8, all subscriptions for the disconnected client will be lost and resubscribing in the
next session will be required to receive updates for any parameters of interest.
Inactivity on an open TCP or UDP port may eventually cause the connection to be terminated by the AZM4/AZM8. To avoid this, it is advised to send a
keep-alive message at least once every 5 minutes. Responses to the keep-alive message are delivered via both TCP and UDP.

Keep-alive message example:
{“jsonrpc”:”2.0”,”method”:”get”,”params”:{“param”:”KeepAlive”,”fmt”:”str”}}
{“jsonrpc”:”2.0”,”method”:”getResp”,”params”:[{“param”:”KeepAlive”,”str”:”OK”}]}  <- TCP Response
{“jsonrpc”:”2.0”,”method”:”getResp”,”params”:[{“param”:”KeepAlive”,”str”:”OK”}]}  <- UDP Response


3.0 Message Types and Syntax
All messages sent to the AZM4/AZM8 must be newline delimited, i.e., “\n” as the last 2 characters of the message. Messages sent to the AZM4/AZM8
include those with methods “set”, “bmp” (bump), “sub” (subscribe), “unsub” (unsubscribe), and “get” (get). Messages sent back to the third-party
client use methods “update”, “getResp” (get response), and “error”.



3.2 Subscribe and Unsubscribe
Messages that use the “sub”, “unsub”, and “get” methods share the same format and have interchangeable parts as shown in the image below. The
“get” method can be used to find the current value of a parameter at the instance in time when the message is sent; however, it is recommended that
parameters are subscribed in order to maintain synchronization.

3.3 Multiple Parameters in a Single Message (Arrays)
Multiple parameters can be included in any message by building an array for “params” using square brackets.
Examples:
{“jsonrpc”:”2.0”,”method”:”set”,”params”:[{“param”:”ZoneGain_0”,”pct”:50},{“param”:”ZoneGain_1”,”val”:-20}]}\n
{“jsonrpc”:”2.0”,”method”:”bmp”,”params”:[{“param”:”SourceGain_0”,”val”:-1},{“param”:”SourceGain_1”,”val”:2}]}\n
{“jsonrpc”:”2.0”,”method”:”sub”,”params”:[{“param”:”SourceMeter_0”,”fmt”:”val”},{“param”:”SourceMeter_1”,”fmt”:”val”},
{“param”:”SourceMeter_2”,”fmt”:”val “},{“param”:”SourceMeter_3”,”fmt”:”val “},{“param”:”SourceMeter_4”,”fmt”:”val”}]}\n
{“jsonrpc”:”2.0”,”method”:”unsub”,”params”:[{“param”:”SourceMeter_3”,”fmt”:”val”},{“param”:”SourceMeter_4”,”fmt”:”val”}]}\n
3.4 Response when using “id”
Some messages do not generate a response from the third-party server. For example, a message using the “unsub” method or messages that use the
“set” and “bmp” when the parameter being modified is not subscribed. However, a response can be generated if desired by appending an “id” to the
end of the message. An example of a message using the “unsub” method with and without an “id” is shown below.
With “id”:
Sent-> {“jsonrpc”:”2.0”,”method”:”unsub”,”params”:{“param”:”GpoPresetName_0”,”val”:”str”},”id”:10}\n
Received-> {“jsonrpc”:”2.0”,”result”:”OK”,”id”:10}
Without “id”:
Sent-> {“jsonrpc”:”2.0”,”method”:”unsub”,”params”:{“param”:”GpoPresetName_0”,”val”:”str”}}\n
Nothing Received
4.0 Parameters with Special Handling
Some third-party parameters have restrictions or require special handling; those parameters are described here.
	•Parameters that contain the names (SourceName, ZoneName, MixName, etc.) cannot be set by a third-party client. The only valid actions for
these parameters is “sub” (subscribe), “unsub” (unsubscribe) and “get”.
	•The GroupActive parameter can be set in order to Activate (Combine) or Deactivate (Uncombine) Zones just like the Combine buttons seen
in the Groups section of the Zones tab in the GUI. It can also be subscribed in order to know the current Combine state. The ZoneActive
parameter can be subscribed and indicates when a Zone is included in a Group; however, it cannot be set by a third-party client.
	•Action parameters (PlayMessage, RecallScene, etc…) will trigger the associated action when included in a properly formatted message
using the “set” or “bmp” method; however, the value of these parameters does not represent the action state. These parameters are not
really meant for subscription, but if the parameter is subscribed in a session, an update will be received when the parameter is acted upon.
Receiving an update after the initial subscription indicates the action has been triggered.


5.0 Third Party Control Message Table
The Third Party Control Message Table shows how third-party parameter names correspond to parameters in the AZM4/AZM8’s configuration. The table
can be found in the User Interface under [Settings > Third Party Controller > Message Table].
To find the name of a third-party parameter:
	1. Look in the “Names” column to find the Source, Zone, Group, etc… of interest. (This column shows names that were assigned during the
setup of the AZM4/AZM8)
	2. Follow the row over to the parameter attribute of interest (Gain, Mute, etc…)
	3. Note the third party param name in the row/column intersection
	For example, to send a message to mute the source called “Big Mic” in the AZM4/AZM8, follow the “Big Mic” row (in the Sources section)
to the “Mute” column to find the third party param name “SourceMute_2”. Then construct the desired message:
{“jsonrpc”:”2.0”,”method”:”set”,”params”:{“param”:”SourceMute_2”,”val”:1}}\n

Note: The Third Party Message Table is dynamic and will update according to the current AZM4/AZM8 settings.


6.0 Parameter List
General parameter names (without the underscore and index) are shown with their ranges in the table below.




