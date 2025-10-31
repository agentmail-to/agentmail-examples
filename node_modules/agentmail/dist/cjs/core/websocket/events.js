"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CloseEvent = exports.ErrorEvent = exports.Event = void 0;
class Event {
    constructor(type, target) {
        this.target = target;
        this.type = type;
    }
}
exports.Event = Event;
class ErrorEvent extends Event {
    constructor(error, target) {
        super("error", target);
        this.message = error.message;
        this.error = error;
    }
}
exports.ErrorEvent = ErrorEvent;
class CloseEvent extends Event {
    constructor(code = 1000, reason = "", target) {
        super("close", target);
        this.wasClean = true;
        this.code = code;
        this.reason = reason;
    }
}
exports.CloseEvent = CloseEvent;
