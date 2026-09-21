import UIKit

// Manual entry rather than `@main` on the app delegate: work that must finish
// before UIKit reads saved sessions has to run here. Background resumes do
// not enter `main`, so a live scene is left alone. Not on Mac Catalyst, where
// the same folder is AppKit's and holds the window frames.
#if !targetEnvironment(macCatalyst)
do {
    if let bundleIdentifier = Bundle.main.bundleIdentifier {
        let library = try FileManager.default.url(
            for: .libraryDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: false
        )
        try SceneRestorationReset.removeSavedState(
            in: library,
            bundleIdentifier: bundleIdentifier
        )
    }
} catch {
    NSLog("Could not clear saved scene state: %@", String(describing: error))
}
#endif

UIApplicationMain(
    CommandLine.argc,
    CommandLine.unsafeArgv,
    nil,
    NSStringFromClass(AppDelegate.self)
)
