---
name: websockets
description: Implement WebSocket connections for real-time features. Use when the user asks to add real-time updates, implement a chat feature, push live notifications, add a live dashboard, set up Socket.IO, use the WebSocket API, implement pub/sub over a socket, or scale WebSockets across multiple server instances.
---

# WebSockets

Build real-time features that are reliable, authenticated, and scale beyond a single server
process. Read the existing transport layer and auth setup before writing anything.

## Ground rules

- **Read the existing stack first.** Check whether Socket.IO, ws, or a native WebSocket
  server is already in use. Don't introduce a second library.
- **Authenticate before upgrading.** The HTTP upgrade request is the last chance to reject
  an unauthenticated connection cleanly. Never let anonymous sockets into authenticated
  namespaces.
- **Handle disconnection explicitly.** Every connection will eventually drop. Clean up
  state, subscriptions, and room memberships on disconnect.
- **Never trust the client.** Validate every message payload server-side, the same way
  you would an HTTP request body.
- **Plan for scale from the start.** In-memory state doesn't survive restarts and doesn't
  work across multiple instances. Use Redis pub/sub for multi-instance deployments.

---

## Step 0: Read the existing setup

```bash
# Existing WebSocket or real-time libraries
grep -r "socket\.io\|\"ws\"\|websocket\|pusher\|ably\|centrifuge" \
  --include="*.json" --include="*.ts" --include="*.js" --include="*.py" -l | head -10

# Is Redis already available?
grep -r "redis\|ioredis" --include="*.ts" --include="*.js" -l | head -5
cat docker-compose.yml | grep -A5 redis
```

---

## Node.js with Socket.IO

Socket.IO is the right default for most Node.js real-time features — it handles
reconnection, rooms, and namespaces out of the box.

### Setup

```ts
import { createServer } from "http";
import { Server, Socket } from "socket.io";
import express from "express";

const app = express();
const httpServer = createServer(app);

const io = new Server(httpServer, {
  cors: {
    origin: process.env.CLIENT_ORIGIN ?? "http://localhost:3000",
    credentials: true,
  },
  // Tune for your load: default ping interval keeps idle connections alive
  pingInterval: 25_000,
  pingTimeout: 20_000,
});

httpServer.listen(3000);
```

### Authentication on connect

Authenticate during the handshake — before the connection is established:

```ts
import jwt from "jsonwebtoken";

io.use((socket, next) => {
  // Accept token from auth handshake or cookie
  const token =
    socket.handshake.auth?.token ??
    socket.handshake.headers.cookie
      ?.split(";")
      .find((c) => c.trim().startsWith("accessToken="))
      ?.split("=")[1];

  if (!token) return next(new Error("Authentication required"));

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET!, {
      algorithms: ["HS256"],
    }) as { sub: string; role: string };

    // Attach user to socket for use in handlers
    (socket as any).user = payload;
    next();
  } catch {
    next(new Error("Invalid token"));
  }
});
```

### Connection and event handlers

```ts
io.on("connection", (socket: Socket) => {
  const user = (socket as any).user as { sub: string; role: string };

  // Join a personal room so you can target this user directly
  socket.join(`user:${user.sub}`);

  console.log(`[ws] connected: ${user.sub} (${socket.id})`);

  // Validate incoming messages — never trust the client
  socket.on("chat:send", (data: unknown) => {
    if (!isValidChatMessage(data)) {
      socket.emit("error", { code: "INVALID_PAYLOAD", message: "Invalid message format" });
      return;
    }
    handleChatMessage(socket, user, data);
  });

  socket.on("room:join", (roomId: unknown) => {
    if (typeof roomId !== "string" || !roomId.match(/^[a-z0-9-]{1,64}$/)) {
      socket.emit("error", { code: "INVALID_ROOM", message: "Invalid room ID" });
      return;
    }
    socket.join(`room:${roomId}`);
    socket.to(`room:${roomId}`).emit("room:user_joined", { userId: user.sub });
  });

  socket.on("disconnect", (reason) => {
    console.log(`[ws] disconnected: ${user.sub} — ${reason}`);
    // Clean up any state tied to this socket
    cleanupUserPresence(user.sub, socket.id);
  });
});
```

### Sending events from outside a socket handler

```ts
// Target a specific user (works across rooms)
io.to(`user:${userId}`).emit("notification:new", { message: "You have a new message" });

// Broadcast to a room
io.to(`room:${roomId}`).emit("chat:message", payload);

// Broadcast to everyone except the sender
socket.broadcast.to(`room:${roomId}`).emit("chat:message", payload);

// Send from an HTTP route handler (e.g., after a DB write)
app.post("/api/orders/:id/complete", async (req, res) => {
  const order = await completeOrder(req.params.id);
  io.to(`user:${order.userId}`).emit("order:completed", { orderId: order.id });
  res.json(order);
});
```

---

## Scaling across multiple instances with Redis adapter

In-memory Socket.IO state (rooms, connected sockets) is not shared across processes.
Use the Redis adapter so events and room broadcasts work across all instances:

```ts
import { createAdapter } from "@socket.io/redis-adapter";
import { createClient } from "redis";

const pubClient = createClient({ url: process.env.REDIS_URL });
const subClient = pubClient.duplicate();

await Promise.all([pubClient.connect(), subClient.connect()]);

io.adapter(createAdapter(pubClient, subClient));
```

That's it — room joins, broadcasts, and `io.to(userId)` now work correctly whether the
sender and receiver are connected to the same instance or different ones.

---

## Client-side (browser)

```ts
import { io, Socket } from "socket.io-client";

const socket: Socket = io("https://api.example.com", {
  auth: { token: getAccessToken() },  // sent in handshake
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
});

socket.on("connect", () => {
  console.log("connected:", socket.id);
});

socket.on("connect_error", (err) => {
  if (err.message === "Authentication required" || err.message === "Invalid token") {
    // Token expired — refresh and reconnect
    refreshToken().then((newToken) => {
      socket.auth = { token: newToken };
      socket.connect();
    });
  }
});

socket.on("disconnect", (reason) => {
  if (reason === "io server disconnect") {
    // Server intentionally disconnected (e.g. banned) — don't auto-reconnect
    console.warn("Disconnected by server");
  }
  // Other reasons: Socket.IO reconnects automatically
});

// Clean up on component unmount / page unload
function cleanup() {
  socket.disconnect();
}
```

---

## Native WebSocket (no Socket.IO)

Use the `ws` library when you need a lightweight server without Socket.IO's overhead, or
when clients are non-browser (IoT devices, other services):

```ts
import { WebSocketServer, WebSocket } from "ws";
import { IncomingMessage } from "http";
import { parse } from "url";

const wss = new WebSocketServer({ noServer: true });

// Attach to an existing HTTP server (share port with Express)
httpServer.on("upgrade", (req: IncomingMessage, socket, head) => {
  const { pathname } = parse(req.url ?? "/");
  if (pathname !== "/ws") {
    socket.destroy();
    return;
  }

  // Authenticate before upgrading
  const user = authenticateUpgradeRequest(req);
  if (!user) {
    socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
    socket.destroy();
    return;
  }

  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit("connection", ws, req, user);
  });
});

wss.on("connection", (ws: WebSocket, req: IncomingMessage, user: AuthUser) => {
  ws.on("message", (data) => {
    let msg: unknown;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      ws.close(1003, "Invalid JSON");
      return;
    }
    handleMessage(ws, user, msg);
  });

  ws.on("close", (code, reason) => {
    cleanup(user.id);
  });

  ws.on("error", (err) => {
    logger.error({ err, userId: user.id }, "WebSocket error");
  });

  // Keep-alive ping
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.ping();
  }, 30_000);

  ws.on("close", () => clearInterval(pingInterval));
});
```

---

## Common mistakes and fixes

| Mistake | Fix |
| --- | --- |
| No auth on the upgrade request | Verify the token in `io.use()` middleware or the `upgrade` handler before accepting |
| Trusting client message payloads | Validate every field server-side; close with `1003` on invalid data |
| Storing connected socket IDs in a DB or in-process Map for multi-instance routing | Use Socket.IO rooms + Redis adapter; let the adapter handle routing |
| Not cleaning up on `disconnect` | Always handle the `disconnect` / `close` event; remove rooms, presence state, timers |
| Broadcasting sensitive data to a room without checking membership | Verify the user is authorised to join/receive before emitting |
| Forgetting to clear `setInterval` ping timers | Store the interval reference and clear it in the `close` handler |
| Reconnecting on a server-initiated disconnect | Check `reason === "io server disconnect"` and don't auto-reconnect |

---

## Checklist

- [ ] Authentication happens before the connection is accepted (handshake middleware)
- [ ] Every incoming message payload is validated server-side
- [ ] Users are joined to a personal room (`user:<id>`) for targeted delivery
- [ ] `disconnect` / `close` handler cleans up state, rooms, and timers
- [ ] Redis adapter installed for multi-instance deployments
- [ ] Client handles `connect_error` with token refresh logic
- [ ] Keep-alive pings configured (Socket.IO default or manual `ws.ping()`)
- [ ] CORS origin is restricted to known client origins, not `*`
- [ ] Rate limiting applied to high-frequency message events (e.g. chat:send)
