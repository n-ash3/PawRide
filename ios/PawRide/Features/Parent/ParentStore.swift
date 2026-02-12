import Foundation

@MainActor
final class ParentStore: ObservableObject {
    @Published var dogs: [DogProfile] = []
    @Published var rides: [Ride] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let api = APIClient.shared

    func refresh(accessToken: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            async let dogsTask = api.fetchDogs(accessToken: accessToken)
            async let ridesTask = api.fetchRides(accessToken: accessToken)
            dogs = try await dogsTask
            rides = try await ridesTask
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func requestRide(
        dogID: String,
        pickupAddress: String,
        dropoffAddress: String,
        dropoffType: String,
        accessToken: String
    ) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            _ = try await api.requestRide(
                payload: RideRequestPayload(
                    dogID: dogID,
                    pickupAddress: pickupAddress,
                    dropoffAddress: dropoffAddress,
                    dropoffType: dropoffType,
                    distanceKM: 3.0,
                    durationMinutes: 12.0,
                    autoDispatch: true
                ),
                accessToken: accessToken
            )
            rides = try await api.fetchRides(accessToken: accessToken)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
