import SwiftUI

struct DriverTabView: View {
    var body: some View {
        TabView {
            DriverHomeView()
                .tabItem { Label("Home", systemImage: "car.rear.fill") }
            DriverEarningsView()
                .tabItem { Label("Earnings", systemImage: "dollarsign.circle.fill") }
            DriverRideHistoryView()
                .tabItem { Label("Ride History", systemImage: "clock.arrow.circlepath") }
            DriverDocumentsView()
                .tabItem { Label("Documents", systemImage: "doc.text.fill") }
            DriverSettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}
