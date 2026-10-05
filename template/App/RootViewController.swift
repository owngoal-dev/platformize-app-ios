import UIKit

/// The first screen: replace it with the app. It shows the one thing every
/// app here has to get right first, which backend it is running with.
final class RootViewController: UIViewController {
    private let titleLabel = UILabel()
    private let statusLabel = UILabel()
    private let client = DaemonClient()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        titleLabel.text = "@APP_NAME@"
        titleLabel.font = .preferredFont(forTextStyle: .largeTitle)
        titleLabel.adjustsFontForContentSizeCategory = true
        titleLabel.accessibilityTraits = .header
        statusLabel.text = String(localized: "Connecting…")
        statusLabel.font = .preferredFont(forTextStyle: .body)
        statusLabel.adjustsFontForContentSizeCategory = true
        statusLabel.textColor = .secondaryLabel
        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center

        let stack = UIStackView(arrangedSubviews: [titleLabel, statusLabel])
        stack.axis = .vertical
        stack.alignment = .center
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerYAnchor.constraint(equalTo: view.safeAreaLayoutGuide.centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: view.layoutMarginsGuide.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: view.layoutMarginsGuide.trailingAnchor),
        ])

        client.hello { [weak self] root in
            guard let self else { return }
            if let root {
                self.statusLabel.text = String(localized: "Privileged backend at \(root)")
            } else {
                self.statusLabel.text = String(localized: "Running without the privileged backend")
            }
        }
    }
}
