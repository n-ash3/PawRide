import SwiftUI

struct AdminTabView: View {
    var body: some View {
        TabView {
            AdminDashboardView()
                .tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }
            AdminRidesView()
                .tabItem { Label("Rides", systemImage: "car.fill") }
            AdminUsersView()
                .tabItem { Label("Users", systemImage: "person.3.fill") }
            AdminAnalyticsView()
                .tabItem { Label("Analytics", systemImage: "chart.pie.fill") }
            AdminSettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}
