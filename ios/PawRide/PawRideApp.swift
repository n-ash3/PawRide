import SwiftUI

@main
struct PawRideApp: App {
    @StateObject private var authStore = AuthStore()

    var body: some Scene {
        WindowGroup {
            RootAppView()
                .environmentObject(authStore)
        }
    }
}

struct RootAppView: View {
    @EnvironmentObject private var authStore: AuthStore

    var body: some View {
        Group {
            if authStore.isAuthenticated {
                RoleRootView()
            } else {
                AuthFlowView()
            }
        }
        .tint(PawRideTheme.primary)
    }
}
