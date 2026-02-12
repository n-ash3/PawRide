import Foundation

enum AppRole: String, Codable, CaseIterable, Identifiable {
    case dogParent = "dog_parent"
    case driver = "driver"
    case admin = "admin"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .dogParent: return "Dog Parent"
        case .driver: return "Driver"
        case .admin: return "Admin"
        }
    }
}

struct AppUser: Codable, Identifiable {
    let id: String
    let phoneNumber: String
    let name: String?
    let photoURL: String?
    var activeRole: AppRole
    let roles: [AppRole]

    enum CodingKeys: String, CodingKey {
        case id
        case phoneNumber = "phone_number"
        case name
        case photoURL = "photo_url"
        case activeRole = "active_role"
        case roles
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let user: AppUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case user
    }
}

struct OTPRequestResponse: Codable {
    let message: String
    let otpExpiresInMinutes: Int
    let devCode: String?

    enum CodingKeys: String, CodingKey {
        case message
        case otpExpiresInMinutes = "otp_expires_in_minutes"
        case devCode = "dev_code"
    }
}

struct DogProfile: Codable, Identifiable {
    let id: String
    let name: String
    let breed: String?
    let size: String
    let photoURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case breed
        case size
        case photoURL = "photo_url"
    }
}

struct Ride: Codable, Identifiable {
    let id: String
    let status: String
    let pickupAddress: String
    let dropoffAddress: String
    let dropoffType: String
    let fareTotal: Double
    let cameraStreamURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case pickupAddress = "pickup_address"
        case dropoffAddress = "dropoff_address"
        case dropoffType = "dropoff_type"
        case fareTotal = "fare_total"
        case cameraStreamURL = "camera_stream_url"
    }
}

struct RideRequestPayload: Codable {
    let dogID: String
    let pickupAddress: String
    let dropoffAddress: String
    let dropoffType: String
    let distanceKM: Double
    let durationMinutes: Double
    let autoDispatch: Bool

    enum CodingKeys: String, CodingKey {
        case dogID = "dog_id"
        case pickupAddress = "pickup_address"
        case dropoffAddress = "dropoff_address"
        case dropoffType = "dropoff_type"
        case distanceKM = "distance_km"
        case durationMinutes = "duration_minutes"
        case autoDispatch = "auto_dispatch"
    }
}

struct DriverDispatchOffer: Codable, Identifiable {
    let id: Int
    let rideID: String
    let distanceKM: Double
    let expiresAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case rideID = "ride_id"
        case distanceKM = "distance_km"
        case expiresAt = "expires_at"
    }
}
