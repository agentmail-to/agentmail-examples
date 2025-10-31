import type * as events from "./events.mjs";
import type * as ws from "./ws.mjs";
export type ReconnectingWebSocket = typeof ws.ReconnectingWebSocket;
export declare namespace ReconnectingWebSocket {
    type Event = events.Event;
    type CloseEvent = events.CloseEvent;
    type ErrorEvent = events.ErrorEvent;
}
