import Foundation

@MainActor
final class DriverStore: ObservableObject {
    @Published var isOnline = false
    @Published var offers: [DriverDispatchOffer] = []
    @Published var earningsSummary: [String: Double] = [:]
    @Published var errorMessage: String?

    private let api = APIClient.shared

    func refresh(accessToken: String) async {
        do {
            async let offersTask = api.fetchDriverOffers(accessToken: accessToken)
            async let earningsTask = api.fetchDriverEarnings(accessToken: accessToken)
            offers = try await offersTask
            earningsSummary = try await earningsTask
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func setOnline(_ value: Bool, accessToken: String) async {
        do {
            try await api.setDriverOnline(isOnline: value, accessToken: accessToken)
            isOnline = value
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func acceptOffer(_ offer: DriverDispatchOffer, accessToken: String) async {
        do {
            try await api.respondToOffer(rideID: offer.rideID, accept: true, accessToken: accessToken)
            offers.removeAll(where: { $0.id == offer.id })
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
