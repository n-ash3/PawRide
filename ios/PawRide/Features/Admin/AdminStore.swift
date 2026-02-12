import Foundation

@MainActor
final class AdminStore: ObservableObject {
    @Published var overview: [String: Double] = [:]
    @Published var errorMessage: String?

    func refresh(accessToken: String) async {
        do {
            overview = try await APIClient.shared.adminOverview(accessToken: accessToken)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
