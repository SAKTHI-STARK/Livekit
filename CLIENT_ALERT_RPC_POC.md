# Client Alert RPC - POC Implementation

## Overview
This is a proof-of-concept (POC) implementation that allows the agent to trigger browser alerts on the client via LiveKit's RPC (Remote Procedure Call) mechanism.

## Architecture

### Backend (Agent)
- **File**: `livekit-voice-agent/agent.py`
- **New Tool**: `client_alert(context: RunContext, message: str) -> str`
- **How it works**:
  1. Agent calls `client_alert` function tool
  2. Tool extracts the room context and finds the user participant
  3. Uses `local_participant.perform_rpc()` to invoke `show_alert` method on the client
  4. Payload is the alert message string

### Frontend (Client)
- **File**: `agents-playground/src/components/playground/Playground.tsx`
- **New RPC Handler**: `show_alert`
- **How it works**:
  1. On room connection, registers RPC method `show_alert`
  2. Handler receives `RpcInvocationData` containing the agent's payload
  3. Displays browser alert via `window.alert(message)`
  4. Returns confirmation string to agent

## Code Changes

### Backend Changes
```python
@function_tool()
async def client_alert(self, context: RunContext, message: str) -> str:
    """Send a client-side alert via RPC."""
    # 1. Extract room and participant info from context
    # 2. Find user participant (not the agent)
    # 3. Call perform_rpc with method="show_alert" and payload=message
    # 4. Return response
```

**Key Points**:
- Uses `perform_rpc()` to invoke a method on the client
- Method name is `show_alert`
- Payload is just the message string
- Handles errors gracefully

### Frontend Changes
```typescript
useEffect(() => {
  if (!room) return;
  
  const handleShowAlert = async (data: any) => {
    // data.payload contains the alert message from the agent
    const message = data.payload || "Alert from agent";
    if (typeof window !== "undefined") {
      window.alert(message);
    }
    return "Alert displayed";
  };

  try {
    room.localParticipant.registerRpcMethod("show_alert", handleShowAlert);
  } catch (err) {
    console.error("Failed to register RPC method show_alert:", err);
  }

  return () => {
    try {
      room.localParticipant.unregisterRpcMethod("show_alert");
    } catch (err) {}
  };
}, [room]);
```

**Key Points**:
- Registers handler in Playground component (has access to room)
- Handler must be async and return a string
- Receives `RpcInvocationData` with `payload` property
- Cleans up on unmount or room change

## Testing

### Quick Test Steps

1. **Start the agent worker**:
   ```bash
   cd livekit-voice-agent
   python agent.py
   ```

2. **Start the frontend**:
   ```bash
   cd agents-playground
   npm run dev
   ```

3. **Trigger an alert** (Option A - Automatic):
   - Add temporary code to `livekit-voice-agent/agent/EnglishAgent.py`:
   ```python
   async def on_enter(self) -> None:
       await self.session.say(IPrompts.first_msg)
       # POC test - call client alert
       try:
           await self.client_alert(None, "🎉 Agent connected successfully!")
       except Exception as e:
           print("Alert failed:", e)
   ```

4. **Trigger an alert** (Option B - via LLM):
   - The agent's LLM can call `client_alert` as a tool if needed
   - Or manually trigger via the agent's logic

5. **Observe**:
   - Browser alert should pop up with the message
   - Agent receives response confirming alert was shown

### Testing RPC Connection
To verify the RPC is working:
1. Open browser dev console (F12)
2. Look for `registerRpcMethod` debug info
3. When alert is triggered, check console for any errors
4. Browser alert should appear with the message

## Data Flow

```
Agent (Backend)                          Client (Frontend)
    |                                        |
    |-- client_alert(message) -->           |
    |                                        |
    |-- perform_rpc("show_alert") -------> |
    |                                   register RPC handler
    |                                        |
    |                        handleShowAlert(data)
    |                                        |
    |                                   window.alert()
    |                                        |
    |<------ RPC Response -------------------|
    |
    |-- return status
```

## Future Enhancements

1. **Toast Instead of Alert**:
   - Replace `window.alert()` with app's `ToasterProvider` for non-blocking UX
   
2. **Rich Formatting**:
   - Support JSON payload for icon, title, severity level
   - Example: `{"type": "success", "title": "Complete", "message": "..."}`

3. **Progress/Status Updates**:
   - Use RPC to send real-time status updates
   - Multiple `show_alert` calls for multi-step workflows

4. **Two-Way RPC**:
   - Client could call back to agent RPC methods
   - Enable bidirectional tool execution

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No user participant found" | Ensure user is connected to room before agent tries to send alert |
| "Session not available" | Make sure `client_alert` is called within agent session context |
| Alert doesn't show | Check browser console for errors; verify RPC handler registered |
| Type errors in TypeScript | Ensure `data: any` or import proper `RpcInvocationData` type from livekit-client |

## References

- LiveKit RPC Documentation: https://docs.livekit.io/agents/rpc/
- LiveKit Client SDK: `livekit-client` npm package
- LiveKit Agents SDK: Python `livekit` package
