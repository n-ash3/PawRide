import Foundation

@MainActor
final class RealtimeService: ObservableObject {
    @Published var lastEvent: String = ""
    @Published var isConnected = false

    private var task: URLSessionWebSocketTask?

    func connectRideChannel(baseURL: URL, rideID: String, accessToken: String) {
        disconnect()
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { return }
        components.scheme = components.scheme == "https" ? "wss" : "ws"
        components.path = "/ws/rides/\(rideID)"
        components.queryItems = [URLQueryItem(name: "token", value: accessToken)]
        guard let wsURL = components.url else { return }

        task = URLSession.shared.webSocketTask(with: wsURL)
        task?.resume()
        isConnected = true
        receiveLoop()
    }

    func disconnect() {
        task?.cancel(with: .normalClosure, reason: nil)
        task = nil
        isConnected = false
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            Task { @MainActor in
                switch result {
                case .failure(let error):
                    self.lastEvent = "Realtime error: \(error.localizedDescription)"
                    self.isConnected = false
                case .success(let message):
                    switch message {
                    case .string(let text):
                        self.lastEvent = text
                    case .data(let data):
                        self.lastEvent = String(data: data, encoding: .utf8) ?? "Binary message"
                    @unknown default:
                        self.lastEvent = "Unknown message"
                    }
                    self.receiveLoop()
                }
            }
        }
    }
}
