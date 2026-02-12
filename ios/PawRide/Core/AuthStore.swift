import Foundation
import SwiftUI

@MainActor
final class AuthStore: ObservableObject {
    @Published var accessToken: String?
    @Published var refreshToken: String?
    @Published var user: AppUser?
    @Published var lastDevCode: String?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var needsRoleSelection = false

    private let api = APIClient.shared
    private let defaults = UserDefaults.standard

    var isAuthenticated: Bool {
        accessToken != nil && user != nil
    }

    init() {
        restoreSession()
    }

    func requestOTP(phoneNumber: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let response = try await api.requestOTP(phoneNumber: phoneNumber)
            lastDevCode = response.devCode
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func verifyOTP(phoneNumber: String, code: String, name: String?, requestedRoles: [AppRole]) async -> Bool {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let auth = try await api.verifyOTP(
                phoneNumber: phoneNumber,
                code: code,
                name: name,
                requestedRoles: requestedRoles
            )
            accessToken = auth.accessToken
            refreshToken = auth.refreshToken
            user = auth.user
            needsRoleSelection = auth.user.roles.count > 1
            persistSession()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func switchRole(_ role: AppRole) async {
        guard let token = accessToken else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let updatedUser = try await api.switchRole(role: role, accessToken: token)
            user = updatedUser
            needsRoleSelection = false
            persistSession()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func logout() {
        accessToken = nil
        refreshToken = nil
        user = nil
        lastDevCode = nil
        errorMessage = nil
        needsRoleSelection = false
        defaults.removeObject(forKey: "pawride.accessToken")
        defaults.removeObject(forKey: "pawride.refreshToken")
        defaults.removeObject(forKey: "pawride.user")
    }

    private func persistSession() {
        defaults.set(accessToken, forKey: "pawride.accessToken")
        defaults.set(refreshToken, forKey: "pawride.refreshToken")
        if let user, let data = try? JSONEncoder().encode(user) {
            defaults.set(data, forKey: "pawride.user")
        }
    }

    private func restoreSession() {
        accessToken = defaults.string(forKey: "pawride.accessToken")
        refreshToken = defaults.string(forKey: "pawride.refreshToken")
        if let data = defaults.data(forKey: "pawride.user"),
           let decoded = try? JSONDecoder().decode(AppUser.self, from: data) {
            user = decoded
            needsRoleSelection = false
        }
    }
}
