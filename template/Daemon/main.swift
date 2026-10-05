import Darwin
import Dispatch
import Foundation
import XPC

// On demand: launchd starts this when the app looks the Mach service up, and
// it exits a few seconds after the last client is gone.

private let idleExitDelay: DispatchTimeInterval = .seconds(3)
private let executableSuffix = "/usr/libexec/@DAEMON@"
private let queue = DispatchQueue(label: "@DAEMON_ID@")

// No install prefix is written in Swift: the root is whatever this executable
// was started from, and an unrecognised path refuses to start.
guard let ownPath = executablePath(pid: getpid()), ownPath.hasSuffix(executableSuffix) else {
    NSLog("@DAEMON@: refusing to start from an unrecognised path")
    exit(EX_CONFIG)
}
private let installRoot = String(ownPath.dropLast(executableSuffix.count))
private let authenticator = PeerAuthenticator(installRoot: installRoot)

private var peers = 0
private var idleGeneration = 0

private func scheduleIdleExit() {
    idleGeneration += 1
    let generation = idleGeneration
    queue.asyncAfter(deadline: .now() + idleExitDelay) {
        if peers == 0 && generation == idleGeneration { exit(EX_OK) }
    }
}

private func handle(_ message: xpc_object_t, from peer: xpc_connection_t) {
    guard xpc_get_type(message) == AppXPC.typeDictionary,
          let operation = xpc_dictionary_get_string(message, AppProtocol.operationKey),
          let reply = xpc_dictionary_create_reply(message) else { return }
    switch String(cString: operation) {
    case AppProtocol.hello:
        xpc_dictionary_set_string(reply, AppProtocol.rootKey, installRoot)
    default:
        return
    }
    xpc_connection_send_message(peer, reply)
}

guard let listener = AppProtocol.serviceName.withCString({
    daemonCreateMachServiceListener($0, queue, machServiceListener)
}) else {
    exit(EX_UNAVAILABLE)
}
xpc_connection_set_event_handler(listener) { peer in
    guard xpc_get_type(peer) == AppXPC.typeConnection else { return }
    guard authenticator.authenticate(peer) else {
        xpc_connection_cancel(peer)
        return
    }
    peers += 1
    idleGeneration += 1
    xpc_connection_set_event_handler(peer) { message in
        guard xpc_get_type(message) != AppXPC.typeError else {
            peers -= 1
            if peers == 0 { scheduleIdleExit() }
            return
        }
        handle(message, from: peer)
    }
    xpc_connection_activate(peer)
}
xpc_connection_activate(listener)
scheduleIdleExit()
dispatchMain()
