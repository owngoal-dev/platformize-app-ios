import Dispatch
import Foundation
import XPC

@_silgen_name("xpc_connection_create_mach_service")
private func appCreateMachServiceConnection(
    _ name: UnsafePointer<CChar>,
    _ queue: DispatchQueue?,
    _ flags: UInt64
) -> xpc_connection_t?

/// Says hello to the daemon. A miss means launchd has not started it yet, so
/// it is retried; only after `gracePeriod`, measured from the first miss, does
/// the app fall back to running without it. Each hello has its own bound,
/// because a daemon launchd cannot start leaves the message queued with no
/// error, and a stale timeout is told apart from a live one by `generation`.
final class DaemonClient {
    private static let gracePeriod: TimeInterval = 10
    private static let helloTimeout: DispatchTimeInterval = .seconds(5)
    private static let retryDelay: DispatchTimeInterval = .seconds(1)

    private let queue = DispatchQueue(label: "@BUNDLE_ID@.client")
    private var firstMiss: Date?
    private var generation = 0

    /// Calls `completion` once, on the main queue, with the install root, or
    /// nil when there is no daemon.
    func hello(_ completion: @escaping (String?) -> Void) {
        queue.async { self.attempt(completion) }
    }

    private func attempt(_ completion: @escaping (String?) -> Void) {
        generation += 1
        let current = generation
        guard let connection = AppProtocol.serviceName.withCString({
            appCreateMachServiceConnection($0, queue, 0)
        }) else {
            missed(completion)
            return
        }
        xpc_connection_set_event_handler(connection) { _ in }
        xpc_connection_activate(connection)

        let request = xpc_dictionary_create(nil, nil, 0)
        xpc_dictionary_set_string(request, AppProtocol.operationKey, AppProtocol.hello)
        xpc_connection_send_message_with_reply(connection, request, queue) { reply in
            guard current == self.generation else { return }
            self.generation += 1
            xpc_connection_cancel(connection)
            if xpc_get_type(reply) == AppXPC.typeDictionary,
               let root = xpc_dictionary_get_string(reply, AppProtocol.rootKey) {
                let value = String(cString: root)
                DispatchQueue.main.async { completion(value.isEmpty ? "/" : value) }
            } else {
                self.missed(completion)
            }
        }
        queue.asyncAfter(deadline: .now() + Self.helloTimeout) {
            guard current == self.generation else { return }
            self.generation += 1
            xpc_connection_cancel(connection)
            self.missed(completion)
        }
    }

    private func missed(_ completion: @escaping (String?) -> Void) {
        let first = firstMiss ?? Date()
        firstMiss = first
        guard Date().timeIntervalSince(first) < Self.gracePeriod else {
            DispatchQueue.main.async { completion(nil) }
            return
        }
        queue.asyncAfter(deadline: .now() + Self.retryDelay) { self.attempt(completion) }
    }
}
