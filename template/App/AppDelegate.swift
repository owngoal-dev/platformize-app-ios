import UIKit

// Not `@main`: `main.swift` clears saved scenes before `UIApplicationMain`.
final class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        ExecutableWatch.start {
            let alert = UIAlertController(
                title: String(localized: "@APP_NAME@ was updated or removed"),
                message: String(localized: "Quit to finish, or keep using this copy until you close it."),
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(title: String(localized: "Later"), style: .cancel))
            alert.addAction(UIAlertAction(title: String(localized: "Quit"), style: .destructive) { _ in
                QuietExit.run()
            })
            let scene = application.connectedScenes.first { $0.activationState == .foregroundActive } as? UIWindowScene
            scene?.keyWindow?.rootViewController?.present(alert, animated: true)
        }
        return true
    }

    func application(
        _ application: UIApplication,
        configurationForConnecting connectingSceneSession: UISceneSession,
        options: UIScene.ConnectionOptions
    ) -> UISceneConfiguration {
        let configuration = UISceneConfiguration(name: nil, sessionRole: connectingSceneSession.role)
        configuration.delegateClass = SceneDelegate.self
        return configuration
    }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let scene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: scene)
        window.rootViewController = RootViewController()
        window.makeKeyAndVisible()
        self.window = window
    }
}
