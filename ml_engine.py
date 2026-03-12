import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_layer_size=100, output_size=1):
        super().__init__()
        self.hidden_layer_size = hidden_layer_size
        self.lstm = nn.LSTM(input_size, hidden_layer_size, batch_first=True)
        self.linear = nn.Linear(hidden_layer_size, output_size)

    def forward(self, input_seq):
        lstm_out, _ = self.lstm(input_seq)
        predictions = self.linear(lstm_out[:, -1, :])
        return predictions

class MLEngine:
    def __init__(self, window_size=60):
        self.window_size = window_size
        self.model = LSTMModel()
        self.scaler = MinMaxScaler(feature_range=(-1, 1))
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)

    def prepare_data(self, data):
        """
        Normalizes data and creates sequences for LSTM.
        """
        scaled_data = self.scaler.fit_transform(data.values.reshape(-1, 1))
        
        sequences = []
        labels = []
        for i in range(len(scaled_data) - self.window_size):
            sequences.append(scaled_data[i:i+self.window_size])
            labels.append(scaled_data[i+self.window_size])
            
        return torch.FloatTensor(np.array(sequences)), torch.FloatTensor(np.array(labels))

    def train_model(self, sequences, labels, epochs=10):
        """
        Trains the LSTM model.
        """
        self.model.train()
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            y_pred = self.model(sequences)
            loss = self.criterion(y_pred, labels)
            loss.backward()
            self.optimizer.step()
            if (epoch+1) % 2 == 0:
                print(f'Epoch {epoch+1} Loss: {loss.item():.6f}')

    def predict(self, last_sequence):
        """
        Predicts the next value.
        """
        self.model.eval()
        with torch.no_grad():
            last_sequence_scaled = self.scaler.transform(last_sequence.reshape(-1, 1))
            last_sequence_tensor = torch.FloatTensor(last_sequence_scaled).view(1, self.window_size, 1)
            prediction_scaled = self.model(last_sequence_tensor)
            prediction = self.scaler.inverse_transform(prediction_scaled.numpy())
            return prediction[0][0]

    def calculate_fibonacci_targets(self, low, high):
        """
        Calculates Fibonacci extension targets (261.8%).
        """
        diff = high - low
        target_261_8 = high + (diff * 2.618)
        return target_261_8

if __name__ == "__main__":
    # Example usage with dummy data
    engine = MLEngine()
    dummy_data = pd.Series(np.random.randn(200).cumsum() + 50000)
    seqs, lbls = engine.prepare_data(dummy_data)
    engine.train_model(seqs, lbls, epochs=5)
    
    last_val_seq = dummy_data.values[-60:]
    pred = engine.predict(last_val_seq)
    print(f"Predicted next price: {pred}")
    
    fib_target = engine.calculate_fibonacci_targets(dummy_data.min(), dummy_data.max())
    print(f"Fibonacci 261.8% target: {fib_target}")
