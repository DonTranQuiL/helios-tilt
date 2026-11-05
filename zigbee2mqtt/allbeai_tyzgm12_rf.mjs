// Zigbee2MQTT external converter: AllbeAI TYZGM12-RF (TS130F / _TZ32981000000_ei4vjkog)
// Shipped in https://github.com/DonTranQuiL/helios-tilt for Helios Tilt users (tested with a Vevor 3000N IP65 20" actuator).
// Time-based position + moving state for a stateless open/close/stop relay controller.
// Uses only public zigbee-herdsman-converters exports (works on Z2M 2.13.x / ZHC 26.90 and 2.14.x / ZHC 26.125).
import * as exposes from 'zigbee-herdsman-converters/lib/exposes';

const e = exposes.presets;
const ea = exposes.access;

const CLUSTER = 'closuresWindowCovering';
const ENDSTOP_EXTRA_MS = 3000; // keep driving past 0/100 so the actuator seats on its limit switch
const MIN_ENDSTOP_RUN_MS = 5000; // explicit OPEN/CLOSE when already at the end: short safe re-seat

const devices = new Map(); // ieeeAddr -> runtime state

const clamp = (v) => Math.min(100, Math.max(0, v));
const num = (v, def, min, max) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : def;
};

function getState(ieee, metaState) {
    let st = devices.get(ieee);
    if (!st) {
        const p = Number(metaState?.position);
        st = {
            currentPos: Number.isFinite(p) ? clamp(p) : 0,
            startPos: 0, targetPos: 0, startTimeMs: 0, durationMs: 0, travelMs: 0,
            direction: 'STOP', timer: null, tickTimer: null, publishFn: null, entity: null, lastPublished: null,
        };
        devices.set(ieee, st);
    }
    return st;
}

function livePos(st, now = Date.now()) {
    if (st.direction === 'STOP') return st.currentPos;
    const moved = ((now - st.startTimeMs) / st.travelMs) * 100;
    return clamp(st.direction === 'UP' ? st.startPos + moved : st.startPos - moved);
}

function payload(st, pos = st.currentPos) {
    const p = Math.round(clamp(pos));
    const state = st.direction === 'UP' || p > 0 ? 'OPEN' : 'CLOSE';
    return {position: p, state, moving: st.direction};
}

function clearTimers(st) {
    if (st.timer) clearTimeout(st.timer);
    if (st.tickTimer) clearInterval(st.tickTimer);
    if (st.safetyTimer) clearTimeout(st.safetyTimer);
    st.timer = null;
    st.tickTimer = null;
    st.safetyTimer = null;
}

function publishTracked(st, pl) {
    const key = JSON.stringify(pl);
    if (!st.publishFn || key === st.lastPublished) return;
    st.lastPublished = key;
    Promise.resolve(st.publishFn(pl)).catch(() => {});
}

// Freeze the motion at the current interpolated position (no Zigbee traffic).
function freeze(st) {
    if (st.direction !== 'STOP') st.currentPos = livePos(st);
    clearTimers(st);
    st.direction = 'STOP';
}

// Send a WindowCovering command with ZCL default-response ACK (as the built-in TS130F
// tz.cover_state does); if the ACK fails, retry once without waiting for one.
async function sendCmd(entity, cmd, logger) {
    try {
        await entity.command(CLUSTER, cmd, {}, {});
        return true;
    } catch (err) {
        logger?.warning?.(`TYZGM12-RF: ${cmd} not ACKed (${err?.message ?? err}), retrying unacked`);
        try {
            await entity.command(CLUSTER, cmd, {}, {disableDefaultResponse: true});
            return true;
        } catch (err2) {
            logger?.error?.(`TYZGM12-RF: ${cmd} failed: ${err2?.message ?? err2}`);
            return false;
        }
    }
}

// Stop, then a second safety stop 1 s later in case a packet got lost.
// The safety stop is cancelled by clearTimers() if a new move starts within that second.
async function sendStop(entity, logger, st) {
    await sendCmd(entity, 'stop', logger);
    if (st.safetyTimer) clearTimeout(st.safetyTimer);
    st.safetyTimer = setTimeout(() => { st.safetyTimer = null; sendCmd(entity, 'stop', logger).catch(() => {}); }, 1000);
}

const fzTracked = {
    cluster: CLUSTER,
    type: ['attributeReport', 'readResponse'],
    convert: (model, msg, publish, options, meta) => {
        const st = getState(msg.device.ieeeAddr, meta?.state);
        st.publishFn = publish; // stable closure -> publishEntityState(device, payload)
        // Ignore the device's bogus currentPositionLiftPercentage; report our tracked state instead.
        const pl = payload(st, livePos(st));
        st.lastPublished = JSON.stringify(pl);
        return pl;
    },
};

const tzTracked = {
    key: ['state', 'position', 'assumed_position', 'travel_time_open', 'travel_time_close'],
    convertSet: async (entity, key, value, meta) => {
        const ieee = meta.device.ieeeAddr;
        const st = getState(ieee, meta.state);
        if (typeof meta.publish === 'function') st.publishFn = meta.publish;
        st.entity = entity;
        const opts = meta.options ?? {};
        if (key === 'travel_time_open' || key === 'travel_time_close') {
            const v = num(value, NaN, 1, 600);
            if (!Number.isFinite(v)) throw new Error(`TYZGM12-RF: invalid ${key} '${value}'`);
            return {state: {[key]: v}};
        }
        const ms = meta.state ?? {};
        const travelOpenMs = num(ms.travel_time_open ?? opts.travel_time_open, 100, 1, 600) * 1000;
        const travelCloseMs = num(ms.travel_time_close ?? opts.travel_time_close, 100, 1, 600) * 1000;
        const tickMs = num(opts.update_interval, 2, 1, 30) * 1000;
        const invert = opts.invert_motor === true || opts.invert_motor === 'true';

        freeze(st); // any new command first lands the in-flight move where it really is
        const from = st.currentPos;

        if (key === 'assumed_position') {
            st.currentPos = clamp(num(value, from, 0, 100));
            await sendStop(entity, meta.logger, st); // also safely halts anything running
            return {state: {...payload(st), assumed_position: Math.round(st.currentPos)}};
        }

        let target;
        let explicitEnd = false;
        if (key === 'state') {
            const v = String(value).toUpperCase();
            if (v === 'STOP') {
                await sendStop(entity, meta.logger, st);
                return {state: payload(st)};
            }
            if (v === 'OPEN') target = 100;
            else if (v === 'CLOSE') target = 0;
            else throw new Error(`TYZGM12-RF: unsupported state '${value}'`);
            explicitEnd = true;
        } else {
            target = clamp(num(value, from, 0, 100));
            if (Math.abs(target - from) < 0.5 && target !== 0 && target !== 100) {
                await sendStop(entity, meta.logger, st);
                return {state: payload(st)};
            }
            explicitEnd = target === 0 || target === 100;
        }

        const direction = target > from || (target === 100 && explicitEnd) ? 'UP' : 'DOWN';
        const travelMs = direction === 'UP' ? travelOpenMs : travelCloseMs;
        let durationMs = (Math.abs(target - from) / 100) * travelMs;
        if (target === 0 || target === 100) durationMs = Math.max(durationMs + ENDSTOP_EXTRA_MS, MIN_ENDSTOP_RUN_MS);

        const cmd = (direction === 'UP') !== invert ? 'upOpen' : 'downClose';
        if (!(await sendCmd(entity, cmd, meta.logger))) throw new Error(`TYZGM12-RF: ${cmd} failed`);

        Object.assign(st, {startPos: from, targetPos: target, startTimeMs: Date.now(), durationMs, travelMs, direction});
        st.tickTimer = setInterval(() => publishTracked(st, payload(st, livePos(st))), tickMs);
        st.timer = setTimeout(async () => {
            clearTimers(st);
            st.direction = 'STOP';
            st.currentPos = st.targetPos;
            publishTracked(st, payload(st));
            await sendStop(st.entity, meta.logger, st); // device answers with a report -> fzTracked republishes tracked state
        }, durationMs);

        const pl = payload(st, from);
        st.lastPublished = JSON.stringify(pl);
        return {state: pl};
    },
    convertGet: async (entity, key, meta) => {
        const st = getState(meta.device.ieeeAddr, meta.state);
        if (typeof meta.publish === 'function') st.publishFn = meta.publish;
        try { await entity.read(CLUSTER, ['currentPositionLiftPercentage']); } catch { /* ignore */ }
    },
};

export default {
    fingerprint: [{modelID: 'TS130F', manufacturerName: '_TZ32981000000_ei4vjkog'}],
    model: 'TYZGM12-RF',
    vendor: 'AllbeAI',
    description: 'Zigbee + RF motor / linear actuator controller (time-based position & state)',
    fromZigbee: [fzTracked],
    toZigbee: [tzTracked],
    exposes: [
        e.cover_position(),
        e.enum('moving', ea.STATE, ['UP', 'DOWN', 'STOP']).withDescription('Current motor movement state'),
        e.numeric('assumed_position', ea.STATE_SET).withValueMin(0).withValueMax(100).withUnit('%').withCategory('config')
            .withDescription('Override tracked position without moving the motor (e.g. set to 0 when physically closed)'),
        e.numeric('travel_time_open', ea.STATE_SET).withValueMin(1).withValueMax(600).withValueStep(0.5).withUnit('s').withCategory('config')
            .withDescription('Seconds from fully closed (0%) to fully open (100%). Default 100 (tuned for Vevor 3000N IP65 20").'),
        e.numeric('travel_time_close', ea.STATE_SET).withValueMin(1).withValueMax(600).withValueStep(0.5).withUnit('s').withCategory('config')
            .withDescription('Seconds from fully open (100%) to fully closed (0%). Default 100 (tuned for Vevor 3000N IP65 20").'),
    ],
    options: [
        e.numeric('update_interval', ea.SET).withValueMin(1).withValueMax(30).withUnit('s')
            .withDescription('How often the position is published while moving. Default 2.'),
        e.binary('invert_motor', ea.SET, true, false)
            .withDescription('Swap the open/close relay commands if the motor wires are reversed. Default false.'),
    ],
    configure: async (device, coordinatorEndpoint, definition) => {
        const ep = device.getEndpoint(1) ?? device.endpoints[0];
        try { await ep.bind(CLUSTER, coordinatorEndpoint); } catch { /* ignore */ }
        try { await ep.read(CLUSTER, ['currentPositionLiftPercentage']); } catch { /* ignore */ }
    },
    onEvent: async (event) => {
        // ZHC 26.x signature: onEvent({type, data}); 'stop' carries data.ieeeAddr
        if (event?.type === 'stop') {
            const st = devices.get(event.data?.ieeeAddr);
            if (st) { clearTimers(st); if (st.direction !== 'STOP') { st.currentPos = livePos(st); st.direction = 'STOP'; } }
        } else if (event?.type === 'start') {
            const ieee = event.data?.device?.ieeeAddr;
            if (ieee) getState(ieee, event.data?.state);
        }
    },
};
