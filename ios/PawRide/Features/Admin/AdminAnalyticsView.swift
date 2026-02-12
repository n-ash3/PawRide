import SwiftUI

struct AdminAnalyticsView: View {
    var body: some View {
        NavigationStack {
            List {
                Label("Rides by type", systemImage: "chart.bar.xaxis")
                Label("Peak hours", systemImage: "clock")
                Label("Driver utilization", systemImage: "gauge.with.dots.needle.67percent")
                Label("Rating trends", systemImage: "star.leadinghalf.filled")
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Analytics")
        }
    }
}
