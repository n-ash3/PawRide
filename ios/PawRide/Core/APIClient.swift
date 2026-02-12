import Foundation

final class APIClient {
    static let shared = APIClient()

    // Replace with your deployed backend URL.
    var baseURL = URL(string: "http://127.0.0.1:8000")!

    private init() {}

    func requestOTP(phoneNumber: String) async throws -> OTPRequestResponse {
        try await send(
            path: "/auth/request-otp",
            method: "POST",
            body: ["phone_number": phoneNumber],
            token: nil
        )
    }

    func verifyOTP(phoneNumber: String, code: String, name: String?, requestedRoles: [AppRole]) async throws -> AuthResponse {
        let roles = requestedRoles.map(\.rawValue)
        return try await send(
            path: "/auth/verify-otp",
            method: "POST",
            body: [
                "phone_number": phoneNumber,
                "code": code,
                "name": name ?? "",
                "requested_roles": roles
            ],
            token: nil
        )
    }

    func switchRole(role: AppRole, accessToken: String) async throws -> AppUser {
        try await send(
            path: "/auth/switch-role",
            method: "POST",
            body: ["role": role.rawValue],
            token: accessToken
        )
    }

    func fetchDogs(accessToken: String) async throws -> [DogProfile] {
        try await send(path: "/dogs", method: "GET", body: nil, token: accessToken)
    }

    func fetchRides(accessToken: String) async throws -> [Ride] {
        try await send(path: "/rides", method: "GET", body: nil, token: accessToken)
    }

    func requestRide(payload: RideRequestPayload, accessToken: String) async throws -> Ride {
        let body: [String: Any] = [
            "dog_id": payload.dogID,
            "pickup_address": payload.pickupAddress,
            "dropoff_address": payload.dropoffAddress,
            "dropoff_type": payload.dropoffType,
            "distance_km": payload.distanceKM,
            "duration_minutes": payload.durationMinutes,
            "auto_dispatch": payload.autoDispatch
        ]
        return try await send(path: "/rides", method: "POST", body: body, token: accessToken)
    }

    func becomeDriver(accessToken: String) async throws {
        let _: [String: String] = try await send(
            path: "/drivers/become-driver",
            method: "POST",
            body: ["create_profile_if_missing": true],
            token: accessToken
        )
    }

    func setDriverOnline(isOnline: Bool, accessToken: String) async throws {
        let _: [String: Bool] = try await send(
            path: "/drivers/me/online",
            method: "POST",
            body: ["is_online": isOnline],
            token: accessToken
        )
    }

    func fetchDriverOffers(accessToken: String) async throws -> [DriverDispatchOffer] {
        try await send(path: "/drivers/me/offers", method: "GET", body: nil, token: accessToken)
    }

    func fetchDriverEarnings(accessToken: String) async throws -> [String: Double] {
        try await send(path: "/drivers/me/earnings", method: "GET", body: nil, token: accessToken)
    }

    func respondToOffer(rideID: String, accept: Bool, accessToken: String) async throws {
        try await sendVoid(
            path: "/rides/\(rideID)/dispatch/respond",
            method: "POST",
            body: ["accept": accept],
            token: accessToken
        )
    }

    func adminOverview(accessToken: String) async throws -> [String: Double] {
        try await send(path: "/admin/analytics/overview", method: "GET", body: nil, token: accessToken)
    }

    private func send<T: Decodable>(
        path: String,
        method: String,
        body: [String: Any]?,
        token: String?
    ) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown API error"
            throw APIError.server(message)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func sendVoid(
        path: String,
        method: String,
        body: [String: Any]?,
        token: String?
    ) async throws {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        }
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server("Request failed with status code \(httpResponse.statusCode)")
        }
    }
}

enum APIError: Error, LocalizedError {
    case invalidResponse
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid server response."
        case .server(let message):
            return message
        }
    }
}
