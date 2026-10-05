/// The wire between the app and the daemon: a closed list of operations, and
/// never `exec(path, argv)`. Add an operation here, in the daemon's switch and
/// in `AGENTS.md` together.
enum AppProtocol {
    static let serviceName = "@SERVICE_NAME@"
    static let clientEntitlement = "@APP_CLIENT_ENTITLEMENT@"
    /// Executables allowed to connect, relative to the install root.
    static let clientPaths = ["/Applications/@APP_NAME@.app/@APP_NAME@"]

    static let operationKey = "op"
    static let rootKey = "root"

    /// Answers the install root the daemon derived from its own path. The
    /// app is privileged exactly when this answers; it is never a build flag.
    static let hello = "hello"
}
