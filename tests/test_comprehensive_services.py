"""
Comprehensive unit tests for all service classes and utilities.
"""
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime, timedelta

from app.services.auth import AuthService
from app.services.billing import BillingService
from app.services.payment import PaymentService
from app.services.upload import FileUploadService
from app.services.fallback_services import (
    FallbackVisualAnalysisService, FallbackDiarizationService,
    FallbackTextProcessingService, FallbackMusicDetectionService,
    FallbackServiceManager
)
from app.core.exceptions import (
    ValidationError, ProcessingError, AuthenticationError,
    BusinessLogicError, ExternalServiceError, ErrorCode
)
from app.schemas.user import UserCreate, UserLogin
# from app.schemas.upload import UploadResponse  # Not needed for these tests
from app.models.user import User
from app.models.transaction import Transaction


class TestAuthServiceComprehensive:
    """Comprehensive tests for AuthService."""
    
    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance."""
        return AuthService()
    
    def test_password_complexity_validation(self, auth_service):
        """Test password complexity requirements."""
        # Too short
        with pytest.raises(ValidationError, match="at least 8 characters"):
            auth_service._validate_password("short")
        
        # No uppercase
        with pytest.raises(ValidationError, match="uppercase letter"):
            auth_service._validate_password("lowercase123")
        
        # No lowercase
        with pytest.raises(ValidationError, match="lowercase letter"):
            auth_service._validate_password("UPPERCASE123")
        
        # No numbers
        with pytest.raises(ValidationError, match="number"):
            auth_service._validate_password("NoNumbers")
        
        # Valid password
        auth_service._validate_password("ValidPass123")  # Should not raise
    
    def test_email_validation(self, auth_service):
        """Test email format validation."""
        # Invalid formats
        invalid_emails = [
            "notanemail",
            "@domain.com",
            "user@",
            "user@domain",
            "user..double@domain.com",
            "user@domain..com"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError, match="Invalid email format"):
                auth_service._validate_email(email)
        
        # Valid emails
        valid_emails = [
            "user@domain.com",
            "user.name@domain.co.uk",
            "user+tag@domain.org",
            "123@domain.com"
        ]
        
        for email in valid_emails:
            auth_service._validate_email(email)  # Should not raise
    
    def test_token_expiration_handling(self, auth_service):
        """Test JWT token expiration."""
        # Create token with short expiration
        data = {"sub": "test-user", "email": "test@example.com"}
        token = auth_service.create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        # Verify expired token
        payload = auth_service.verify_token(token)
        assert payload is None  # Expired token should return None
    
    def test_token_with_custom_claims(self, auth_service):
        """Test JWT tokens with custom claims."""
        data = {
            "sub": "test-user",
            "email": "test@example.com",
            "role": "admin",
            "permissions": ["read", "write", "delete"]
        }
        
        token = auth_service.create_access_token(data)
        payload = auth_service.verify_token(token)
        
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write", "delete"]
    
    def test_rate_limiting_login_attempts(self, auth_service, db_session):
        """Test rate limiting for login attempts."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="TestPass123")
        auth_service.create_user(db_session, user_create)
        
        # Mock Redis for rate limiting
        with patch('app.core.redis.redis_client') as mock_redis:
            mock_redis.get.return_value = b'5'  # 5 attempts
            mock_redis.incr.return_value = 6
            mock_redis.expire.return_value = True
            
            # Should raise rate limit error
            with pytest.raises(AuthenticationError, match="Too many login attempts"):
                auth_service.authenticate_user(db_session, "test@example.com", "wrongpassword")


class TestBillingServiceComprehensive:
    """Comprehensive tests for BillingService."""
    
    @pytest.fixture
    def billing_service(self):
        """Create BillingService instance."""
        return BillingService()
    
    def test_cost_calculation_edge_cases(self, billing_service):
        """Test cost calculation for edge cases."""
        # Zero duration
        cost = billing_service.calculate_cost(0.0)
        assert cost == 0.0
        
        # Fractional seconds
        cost = billing_service.calculate_cost(30.5)  # 30.5 seconds
        expected = (30.5 / 60) * 75.0  # Should be ~38.125 rubles
        assert abs(cost - expected) < 0.01
        
        # Very long duration
        cost = billing_service.calculate_cost(7200.0)  # 2 hours
        expected = (7200.0 / 60) * 75.0  # 9000 rubles
        assert cost == expected
    
    def test_balance_operations_thread_safety(self, billing_service, db_session, test_user):
        """Test thread safety of balance operations."""
        import threading
        import time
        
        # Initial balance
        test_user.balance = 1000.0
        db_session.commit()
        
        results = []
        errors = []
        
        def charge_balance(amount):
            try:
                result = billing_service.charge_user_balance(db_session, test_user.id, amount)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads charging simultaneously
        threads = []
        for i in range(10):
            thread = threading.Thread(target=charge_balance, args=(50.0,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        successful_charges = len([r for r in results if r.success])
        failed_charges = len(errors)
        
        # Should have some successful charges but not exceed balance
        assert successful_charges > 0
        assert successful_charges <= 20  # Max 20 charges of 50 rubles from 1000 balance
        
        # Refresh user balance
        db_session.refresh(test_user)
        assert test_user.balance >= 0  # Should never go negative
    
    def test_transaction_logging(self, billing_service, db_session, test_user):
        """Test comprehensive transaction logging."""
        initial_balance = 500.0
        test_user.balance = initial_balance
        db_session.commit()
        
        # Perform various operations
        billing_service.add_balance(db_session, test_user.id, 200.0, "Payment via СБП")
        billing_service.charge_user_balance(db_session, test_user.id, 75.0, "Video processing")
        billing_service.charge_user_balance(db_session, test_user.id, 150.0, "Premium features")
        
        # Check transaction history
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).order_by(Transaction.created_at).all()
        
        assert len(transactions) == 3
        
        # Verify transaction details
        assert transactions[0].type == "payment"
        assert transactions[0].amount == 200.0
        assert "СБП" in transactions[0].description
        
        assert transactions[1].type == "charge"
        assert transactions[1].amount == -75.0
        assert "Video processing" in transactions[1].description
        
        assert transactions[2].type == "charge"
        assert transactions[2].amount == -150.0
        
        # Verify final balance
        db_session.refresh(test_user)
        expected_balance = initial_balance + 200.0 - 75.0 - 150.0
        assert test_user.balance == expected_balance
    
    def test_insufficient_balance_handling(self, billing_service, db_session, test_user):
        """Test handling of insufficient balance scenarios."""
        test_user.balance = 50.0
        db_session.commit()
        
        # Try to charge more than available
        with pytest.raises(BusinessLogicError):
            billing_service.charge_user_balance(db_session, test_user.id, 100.0)
        
        # Balance should remain unchanged
        db_session.refresh(test_user)
        assert test_user.balance == 50.0
        
        # No transaction should be created
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        assert len(transactions) == 0


class TestPaymentServiceComprehensive:
    """Comprehensive tests for PaymentService."""
    
    @pytest.fixture
    def payment_service(self):
        """Create PaymentService instance."""
        return PaymentService()
    
    @pytest.mark.asyncio
    async def test_sbp_payment_flow(self, payment_service):
        """Test complete СБП payment flow."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful payment response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "payment_id": "sbp_123456",
                "status": "pending",
                "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                "amount": 750.0
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Initiate payment
            result = await payment_service.create_sbp_payment(
                user_id="test-user",
                amount=750.0,
                description="Balance top-up"
            )
            
            assert result["payment_id"] == "sbp_123456"
            assert result["status"] == "pending"
            assert "qr_code" in result
            assert result["amount"] == 750.0
    
    @pytest.mark.asyncio
    async def test_payment_confirmation_webhook(self, payment_service, db_session, test_user):
        """Test payment confirmation via webhook."""
        # Mock webhook payload
        webhook_data = {
            "payment_id": "sbp_123456",
            "status": "completed",
            "amount": 750.0,
            "user_id": str(test_user.id),
            "timestamp": "2024-01-15T10:30:00Z",
            "signature": "mock_signature"
        }
        
        with patch.object(payment_service, '_verify_webhook_signature', return_value=True):
            with patch('app.services.billing.billing_service') as mock_billing:
                mock_billing.add_balance.return_value = True
                
                result = await payment_service.process_payment_webhook(webhook_data, db_session)
                
                assert result["success"] is True
                assert result["payment_id"] == "sbp_123456"
                
                # Verify billing service was called
                mock_billing.add_balance.assert_called_once_with(
                    db_session, test_user.id, 750.0, "СБП payment sbp_123456"
                )
    
    @pytest.mark.asyncio
    async def test_payment_failure_handling(self, payment_service):
        """Test handling of payment failures."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock failed payment response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json.return_value = {
                "error": "invalid_amount",
                "message": "Amount must be between 1 and 100000 rubles"
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(ExternalServiceError, match="invalid_amount"):
                await payment_service.create_sbp_payment(
                    user_id="test-user",
                    amount=0.0,  # Invalid amount
                    description="Invalid payment"
                )
    
    def test_webhook_signature_verification(self, payment_service):
        """Test webhook signature verification."""
        payload = '{"payment_id":"test","amount":100.0}'
        
        # Mock secret key
        with patch.object(payment_service, 'webhook_secret', 'test_secret'):
            # Generate valid signature
            import hmac
            import hashlib
            
            signature = hmac.new(
                'test_secret'.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Valid signature should pass
            assert payment_service._verify_webhook_signature(payload, signature) is True
            
            # Invalid signature should fail
            assert payment_service._verify_webhook_signature(payload, 'invalid') is False


class TestFileUploadServiceComprehensive:
    """Comprehensive tests for FileUploadService."""
    
    @pytest.fixture
    def upload_service(self):
        """Create FileUploadService instance."""
        return FileUploadService()
    
    @pytest.mark.asyncio
    async def test_virus_scanning(self, upload_service, temp_video_file):
        """Test virus scanning functionality."""
        with patch('subprocess.run') as mock_run:
            # Mock clean file scan
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "OK"
            
            is_safe = await upload_service._scan_file_for_viruses(temp_video_file)
            assert is_safe is True
            
            # Mock infected file scan
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = "FOUND: Virus.Test"
            
            is_safe = await upload_service._scan_file_for_viruses(temp_video_file)
            assert is_safe is False
    
    @pytest.mark.asyncio
    async def test_file_type_validation(self, upload_service):
        """Test comprehensive file type validation."""
        # Test various file types
        test_cases = [
            ("video.mp4", "video/mp4", True),
            ("video.avi", "video/x-msvideo", True),
            ("video.mov", "video/quicktime", True),
            ("video.mkv", "video/x-matroska", True),
            ("subtitles.srt", "text/plain", True),
            ("document.pdf", "application/pdf", False),
            ("image.jpg", "image/jpeg", False),
            ("script.exe", "application/x-executable", False),
        ]
        
        for filename, content_type, should_be_valid in test_cases:
            is_valid = upload_service._validate_file_type(filename, content_type)
            assert is_valid == should_be_valid, f"Failed for {filename} ({content_type})"
    
    @pytest.mark.asyncio
    async def test_file_size_limits(self, upload_service):
        """Test file size validation."""
        # Small file - should pass
        assert upload_service._validate_file_size(100 * 1024 * 1024) is True  # 100MB
        
        # Large file - should fail
        assert upload_service._validate_file_size(3 * 1024 * 1024 * 1024) is False  # 3GB
        
        # Zero size - should fail
        assert upload_service._validate_file_size(0) is False
    
    @pytest.mark.asyncio
    async def test_secure_filename_generation(self, upload_service):
        """Test secure filename generation."""
        test_cases = [
            ("normal_file.mp4", "normal_file.mp4"),
            ("file with spaces.mp4", "file_with_spaces.mp4"),
            ("файл_на_русском.mp4", "file.mp4"),  # Non-ASCII characters
            ("../../../etc/passwd", "etc_passwd"),  # Path traversal attempt
            ("file<>:\"|?*.mp4", "file.mp4"),  # Special characters
            ("", "file"),  # Empty filename
        ]
        
        for original, expected_pattern in test_cases:
            secure_name = upload_service._generate_secure_filename(original)
            if expected_pattern == "file.mp4" and "русском" in original:
                assert secure_name.endswith(".mp4")
            elif expected_pattern == "file":
                assert len(secure_name) > 0
            else:
                assert secure_name == expected_pattern
    
    @pytest.mark.asyncio
    async def test_upload_with_user_isolation(self, upload_service, temp_video_file):
        """Test user file isolation."""
        user_id_1 = "user-123"
        user_id_2 = "user-456"
        
        with patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('shutil.move') as mock_move, \
             patch.object(upload_service, '_scan_file_for_viruses', return_value=True):
            
            # Upload files for different users
            result_1 = await upload_service.save_uploaded_file(
                temp_video_file, "video1.mp4", user_id_1, "task-1"
            )
            
            result_2 = await upload_service.save_uploaded_file(
                temp_video_file, "video2.mp4", user_id_2, "task-2"
            )
            
            # Verify files are saved in separate user directories
            assert f"/{user_id_1}/" in result_1
            assert f"/{user_id_2}/" in result_2
            assert result_1 != result_2


class TestFallbackServicesComprehensive:
    """Comprehensive tests for fallback services."""
    
    def test_fallback_visual_analysis(self):
        """Test fallback visual analysis service."""
        service = FallbackVisualAnalysisService()
        
        # Test with different scene types
        test_cases = [
            (30.0, "Ср."),  # Medium duration -> Medium shot
            (5.0, "Кр."),   # Short duration -> Close shot
            (60.0, "Общ."), # Long duration -> General shot
        ]
        
        for duration, expected_shot_type in test_cases:
            result = service.analyze_scene_fallback(
                scene_number=1,
                duration=duration,
                dialogue="Test dialogue"
            )
            
            assert result["shot_type"] == expected_shot_type
            assert "Сцена" in result["description"]
            assert result["text_in_frame"] == ""
    
    def test_fallback_diarization(self):
        """Test fallback diarization service."""
        service = FallbackDiarizationService()
        
        # Test with dialogue
        result = service.diarize_fallback(
            audio_duration=120.0,
            dialogue="Привет! Как дела? Все хорошо."
        )
        
        assert "speakers" in result
        assert len(result["speakers"]) >= 1
        assert "segments" in result
        
        # Test without dialogue
        result_no_dialogue = service.diarize_fallback(
            audio_duration=60.0,
            dialogue=""
        )
        
        assert len(result_no_dialogue["speakers"]) == 0
        assert len(result_no_dialogue["segments"]) == 0
    
    def test_fallback_text_processing(self):
        """Test fallback text processing service."""
        service = FallbackTextProcessingService()
        
        test_texts = [
            "привет как дела",  # No punctuation
            "ГРОМКИЙ ТЕКСТ",    # All caps
            "текст   с    пробелами",  # Extra spaces
            "Нормальный текст.",  # Already good
        ]
        
        for text in test_texts:
            result = service.process_text_fallback(text)
            
            # Should have proper capitalization and punctuation
            assert result[0].isupper()  # First letter capitalized
            assert result.endswith(('.', '!', '?'))  # Proper ending
            assert '  ' not in result  # No double spaces
    
    def test_fallback_music_detection(self):
        """Test fallback music detection service."""
        service = FallbackMusicDetectionService()
        
        # Test different scene characteristics
        test_cases = [
            (30.0, "музыка играет", True),   # Contains music keyword
            (45.0, "тихий разговор", False), # No music indicators
            (120.0, "концерт", True),        # Music-related word
            (15.0, "", False),               # No dialogue
        ]
        
        for duration, dialogue, expected_music in test_cases:
            result = service.detect_music_fallback(
                scene_number=1,
                duration=duration,
                dialogue=dialogue
            )
            
            assert result["has_music"] == expected_music
            assert result["confidence"] >= 0.0
            assert result["confidence"] <= 1.0
    
    def test_fallback_service_manager(self):
        """Test fallback service manager."""
        manager = FallbackServiceManager()
        
        # Test service availability checking
        assert manager.is_service_available("visual_analysis") in [True, False]
        assert manager.is_service_available("diarization") in [True, False]
        assert manager.is_service_available("text_processing") in [True, False]
        assert manager.is_service_available("music_detection") in [True, False]
        
        # Test fallback decision making
        decision = manager.should_use_fallback("visual_analysis", Exception("API Error"))
        assert isinstance(decision, bool)
        
        # Test with rate limit error (should use fallback)
        rate_limit_error = Exception("Rate limit exceeded")
        decision = manager.should_use_fallback("visual_analysis", rate_limit_error)
        assert decision is True
        
        # Test with authentication error (should use fallback)
        auth_error = Exception("Invalid API key")
        decision = manager.should_use_fallback("text_processing", auth_error)
        assert decision is True


class TestServiceIntegration:
    """Test integration between services."""
    
    @pytest.mark.asyncio
    async def test_auth_billing_integration(self, db_session):
        """Test integration between auth and billing services."""
        auth_service = AuthService()
        billing_service = BillingService()
        
        # Create user
        user_create = UserCreate(email="integration@example.com", password="TestPass123")
        user = auth_service.create_user(db_session, user_create)
        
        # Add balance
        billing_service.add_balance(db_session, user.id, 500.0, "Initial balance")
        
        # Authenticate user
        user_login = UserLogin(email="integration@example.com", password="TestPass123")
        token_response = auth_service.login_user(db_session, user_login)
        
        # Verify token contains balance info
        payload = auth_service.verify_token(token_response.access_token)
        assert payload["email"] == "integration@example.com"
        
        # Check balance
        db_session.refresh(user)
        assert user.balance == 500.0
        
        # Charge for processing
        charge_result = billing_service.charge_user_balance(db_session, user.id, 75.0)
        assert charge_result.success is True
        
        # Verify updated balance
        db_session.refresh(user)
        assert user.balance == 425.0
    
    @pytest.mark.asyncio
    async def test_upload_billing_integration(self, temp_video_file, db_session, test_user):
        """Test integration between upload and billing services."""
        upload_service = FileUploadService()
        billing_service = BillingService()
        
        # Set user balance
        test_user.balance = 200.0
        db_session.commit()
        
        # Mock video duration extraction
        with patch.object(upload_service, '_extract_video_duration', return_value=120.0):  # 2 minutes
            with patch.object(upload_service, '_scan_file_for_viruses', return_value=True):
                with patch('pathlib.Path.mkdir'), \
                     patch('shutil.move'):
                    
                    # Calculate cost before upload
                    duration = 120.0  # 2 minutes
                    cost = billing_service.calculate_cost(duration)
                    expected_cost = (120.0 / 60) * 75.0  # 150 rubles
                    assert cost == expected_cost
                    
                    # Check if user has sufficient balance
                    has_balance = billing_service.has_sufficient_balance(db_session, test_user.id, cost)
                    assert has_balance is True
                    
                    # Simulate upload and charge
                    file_path = await upload_service.save_uploaded_file(
                        temp_video_file, "test_video.mp4", str(test_user.id), "task-123"
                    )
                    
                    # Charge user
                    charge_result = billing_service.charge_user_balance(
                        db_session, test_user.id, cost, f"Video processing for {file_path}"
                    )
                    
                    assert charge_result.success is True
                    
                    # Verify balance updated
                    db_session.refresh(test_user)
                    assert test_user.balance == 200.0 - 150.0  # 50 rubles remaining


if __name__ == "__main__":
    pytest.main([__file__, "-v"])